from typing import Dict, Optional

import httpx
import urlman
from django.db import models, transaction
from django.utils import timezone

from activities.models.fan_out import FanOut
from activities.models.timeline_event import TimelineEvent
from core.html import sanitize_post
from core.ld import canonicalise, format_ld_date, parse_ld_date
from stator.models import State, StateField, StateGraph, StatorModel
from users.models.follow import Follow
from users.models.identity import Identity


class PostStates(StateGraph):
    new = State(try_interval=300)
    fanned_out = State()

    new.transitions_to(fanned_out)

    @classmethod
    async def handle_new(cls, instance: "Post"):
        """
        Creates all needed fan-out objects for a new Post.
        """
        await instance.afan_out()
        return cls.fanned_out


class Post(StatorModel):
    """
    A post (status, toot) that is either local or remote.
    """

    class Visibilities(models.IntegerChoices):
        public = 0
        unlisted = 1
        followers = 2
        mentioned = 3

    # The author (attributedTo) of the post
    author = models.ForeignKey(
        "users.Identity",
        on_delete=models.PROTECT,
        related_name="posts",
    )

    # The state the post is in
    state = StateField(PostStates)

    # If it is our post or not
    local = models.BooleanField()

    # The canonical object ID
    object_uri = models.CharField(max_length=500, blank=True, null=True, unique=True)

    # Who should be able to see this Post
    visibility = models.IntegerField(
        choices=Visibilities.choices,
        default=Visibilities.public,
    )

    # The main (HTML) content
    content = models.TextField()

    # If the contents of the post are sensitive, and the summary (content
    # warning) to show if it is
    sensitive = models.BooleanField(default=False)
    summary = models.TextField(blank=True, null=True)

    # The public, web URL of this Post on the original server
    url = models.CharField(max_length=500, blank=True, null=True)

    # The Post it is replying to as an AP ID URI
    # (as otherwise we'd have to pull entire threads to use IDs)
    in_reply_to = models.CharField(max_length=500, blank=True, null=True)

    # The identities the post is directly to (who can see it if not public)
    to = models.ManyToManyField(
        "users.Identity",
        related_name="posts_to",
        blank=True,
    )

    # The identities mentioned in the post
    mentions = models.ManyToManyField(
        "users.Identity",
        related_name="posts_mentioning",
        blank=True,
    )

    # When the post was originally created (as opposed to when we received it)
    published = models.DateTimeField(default=timezone.now)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class urls(urlman.Urls):
        view = "{self.author.urls.view}posts/{self.id}/"
        view_nice = "{self.author.urls.view_nice}posts/{self.id}/"
        object_uri = "{self.author.actor_uri}posts/{self.id}/"
        action_like = "{view}like/"
        action_unlike = "{view}unlike/"
        action_boost = "{view}boost/"
        action_unboost = "{view}unboost/"

        def get_scheme(self, url):
            return "https"

        def get_hostname(self, url):
            return self.instance.author.domain.uri_domain

    def __str__(self):
        return f"{self.author} #{self.id}"

    @property
    def safe_content(self):
        return sanitize_post(self.content)

    ### Async helpers ###

    async def afetch_full(self):
        """
        Returns a version of the object with all relations pre-loaded
        """
        return await Post.objects.select_related("author", "author__domain").aget(
            pk=self.pk
        )

    ### Local creation ###

    @classmethod
    def create_local(
        cls, author: Identity, content: str, summary: Optional[str] = None
    ) -> "Post":
        with transaction.atomic():
            post = cls.objects.create(
                author=author,
                content=content,
                summary=summary or None,
                sensitive=bool(summary),
                local=True,
            )
            post.object_uri = post.urls.object_uri
            post.url = post.urls.view_nice
            post.save()
        return post

    ### ActivityPub (outbound) ###

    async def afan_out(self):
        """
        Creates FanOuts for a new post
        """
        # Send a copy to all people who follow this user
        post = await self.afetch_full()
        async for follow in post.author.inbound_follows.select_related(
            "source", "target"
        ):
            if follow.source.local or follow.target.local:
                await FanOut.objects.acreate(
                    identity_id=follow.source_id,
                    type=FanOut.Types.post,
                    subject_post=post,
                )
        # And one for themselves if they're local
        if post.author.local:
            await FanOut.objects.acreate(
                identity_id=post.author_id,
                type=FanOut.Types.post,
                subject_post=post,
            )

    def to_ap(self) -> Dict:
        """
        Returns the AP JSON for this object
        """
        value = {
            "type": "Note",
            "id": self.object_uri,
            "published": format_ld_date(self.published),
            "attributedTo": self.author.actor_uri,
            "content": self.safe_content,
            "to": "as:Public",
            "as:sensitive": self.sensitive,
            "url": self.urls.view_nice if self.local else self.url,
        }
        if self.summary:
            value["summary"] = self.summary
        return value

    def to_create_ap(self):
        """
        Returns the AP JSON to create this object
        """
        return {
            "type": "Create",
            "id": self.object_uri + "#create",
            "actor": self.author.actor_uri,
            "object": self.to_ap(),
        }

    ### ActivityPub (inbound) ###

    @classmethod
    def by_ap(cls, data, create=False, update=False) -> "Post":
        """
        Retrieves a Post instance by its ActivityPub JSON object.

        Optionally creates one if it's not present.
        Raises KeyError if it's not found and create is False.
        """
        # Do we have one with the right ID?
        created = False
        try:
            post = cls.objects.get(object_uri=data["id"])
        except cls.DoesNotExist:
            if create:
                # Resolve the author
                author = Identity.by_actor_uri(data["attributedTo"], create=create)
                post = cls.objects.create(
                    object_uri=data["id"],
                    author=author,
                    content=sanitize_post(data["content"]),
                    local=False,
                )
                created = True
            else:
                raise KeyError(f"No post with ID {data['id']}", data)
        if update or created:
            post.content = sanitize_post(data["content"])
            post.summary = data.get("summary", None)
            post.sensitive = data.get("as:sensitive", False)
            post.url = data.get("url", None)
            post.published = parse_ld_date(data.get("published", None))
            # TODO: to
            # TODO: mentions
            # TODO: visibility
            post.save()
        return post

    @classmethod
    def by_object_uri(cls, object_uri, fetch=False):
        """
        Gets the post by URI - either looking up locally, or fetching
        from the other end if it's not here.
        """
        try:
            return cls.objects.get(object_uri=object_uri)
        except cls.DoesNotExist:
            if fetch:
                # Go grab the data from the URI
                response = httpx.get(
                    object_uri,
                    headers={"Accept": "application/json"},
                    follow_redirects=True,
                )
                if 200 <= response.status_code < 300:
                    return cls.by_ap(
                        canonicalise(response.json(), include_security=True),
                        create=True,
                        update=True,
                    )
            raise cls.DoesNotExist(f"Cannot find Post with URI {object_uri}")

    @classmethod
    def handle_create_ap(cls, data):
        """
        Handles an incoming create request
        """
        # Ensure the Create actor is the Post's attributedTo
        if data["actor"] != data["object"]["attributedTo"]:
            raise ValueError("Create actor does not match its Post object", data)
        # Create it
        post = cls.by_ap(data["object"], create=True, update=True)
        # Make timeline events as appropriate
        for follow in Follow.objects.filter(target=post.author, source__local=True):
            TimelineEvent.add_post(follow.source, post)
        # Force it into fanned_out as it's not ours
        post.transition_perform(PostStates.fanned_out)

    @classmethod
    def handle_delete_ap(cls, data):
        """
        Handles an incoming create request
        """
        # Find our post by ID if we have one
        try:
            post = cls.by_object_uri(data["object"]["id"])
        except cls.DoesNotExist:
            # It's already been deleted
            return
        # Ensure the actor on the request authored the post
        if not post.author.actor_uri == data["actor"]:
            raise ValueError("Actor on delete does not match object")
        post.delete()

    def debug_fetch(self):
        """
        Fetches the Post from its original URL again and updates us with it
        """
        response = httpx.get(
            self.object_uri,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        if 200 <= response.status_code < 300:
            return self.by_ap(
                canonicalise(response.json(), include_security=True),
                update=True,
            )