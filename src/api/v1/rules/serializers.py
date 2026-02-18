from rest_framework import serializers

from rules.models import RulesConfigVersion


class RulesConfigUpdateSerializer(serializers.Serializer):
    config = serializers.JSONField()
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class RulesConfigRollbackSerializer(serializers.Serializer):
    target_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class RulesConfigVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    source_version_number = serializers.IntegerField(
        source="source_version.version", read_only=True
    )

    class Meta:
        model = RulesConfigVersion
        fields = (
            "id",
            "version",
            "action",
            "reason",
            "checksum",
            "source_version",
            "source_version_number",
            "created_by",
            "created_by_username",
            "diff",
            "config",
            "created_at",
        )
        read_only_fields = fields


class RuleConfigStateSerializer(serializers.Serializer):
    active_version = serializers.IntegerField(
        source="active_version.version", read_only=True
    )
    cache_key = serializers.CharField(read_only=True)
    checksum = serializers.CharField(read_only=True)
    config = serializers.JSONField(source="active_version.config", read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
