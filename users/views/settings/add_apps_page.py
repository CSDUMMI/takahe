import secrets

from django import forms
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import FormView

from api.models.application import Application
from api.models.token import Token
from users.decorators import identity_required


class AppsForm(forms.Form):
    name = forms.CharField()
    redirect_uri = forms.CharField(initial="urn:ietf:wg:oauth:2.0:oob")
    website = forms.CharField(required=False)
    scopes = forms.MultipleChoiceField(choices=(("read", "read"), ("write", "write")))


@method_decorator(identity_required, name="dispatch")
class AddAppsPage(FormView):
    """Shows a page of the user's apps
    And allows creating new apps and access tokens.
    """

    template_name = "settings/add_apps.html"
    form_class = AppsForm
    success_url = "/settings/apps/add"

    def form_valid(self, form):
        super().form_valid(form)
        print(type(form))
        print(dir(form))
        application = Application.add_app(
            form.cleaned_data["name"],
            form.cleaned_data.get("website", ""),
            form.cleaned_data["redirect_uri"],
        )

        scopes = ",".join(form.cleaned_data["scopes"])

        Token.objects.create(
            application=application,
            user=self.request.user,
            identity=self.request.identity,
            token=secrets.token_urlsafe(43),
            scopes=scopes,
        )

        return redirect("/settings/apps")
