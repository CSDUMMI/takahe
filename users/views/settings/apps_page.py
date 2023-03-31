from django.utils.decorators import method_decorator
from django.views.generic.list import ListView

from api.models.token import Token
from users.decorators import identity_required


@method_decorator(identity_required, name="dispatch")
class AppsPage(ListView):
    model = Token
    template_name = "settings/apps.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        self.object_list = Token.objects.filter(
            user=self.request.user, identity=self.request.identity
        ).prefetch_related("applications")

        return context
