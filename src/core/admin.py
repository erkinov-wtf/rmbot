from unfold.admin import ModelAdmin


class BaseModelAdmin(ModelAdmin): ...


class SoftDeleteModelAdmin(BaseModelAdmin):
    exclude = ("deleted_at",)

    def get_exclude(self, request, obj=None):
        """
        Ensure deleted_at is always excluded, even if subclasses override exclude.
        """
        exclude = super().get_exclude(request, obj)
        if exclude is None:
            exclude = tuple()

        exclude += ("deleted_at",)

        return tuple(exclude)
