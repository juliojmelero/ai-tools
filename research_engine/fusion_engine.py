from research_models.publication import Publication, UnknownPublicationFieldError
from research_engine.provider_priorities import FIELD_RULES


class FusionEngine:

    _METADATA_FIELDS = {"provider", "_providers", "_record"}

    def _validate_fields(self, data):
        unknown = set(data) - set(FIELD_RULES) - self._METADATA_FIELDS
        if unknown:
            fields = ", ".join(sorted(unknown))
            raise UnknownPublicationFieldError(
                f"Unknown publication field(s): {fields}"
            )

    def _dict_to_publication(self, data):
        self._validate_fields(data)
        if "_record" in data:
            return Publication.from_dict(data["_record"])

        pub = Publication()

        provider = data.get("provider")

        for field in FIELD_RULES:
            if field in data:
                pub.add(
                    provider=provider,
                    field_name=field,
                    value=data.get(field),
                )

        return pub

    def _publication_to_flat_dict(self, pub):
        return {
            field: pub.get(field)
            for field in FIELD_RULES
            if pub.get(field) not in (None, "", [], {})
        }

    def merge(self, existing, new):
        self._validate_fields(new)
        if existing is None:
            pub = self._dict_to_publication(new)
        else:
            pub = self._dict_to_publication(existing)

            provider = new.get("provider")

            for field in FIELD_RULES:
                if field in new:
                    pub.add(
                        provider=provider,
                        field_name=field,
                        value=new.get(field),
                    )

        flat = self._publication_to_flat_dict(pub)

        providers = set()

        for p in existing.get("_providers", []) if existing else []:
            providers.add(p)

        if existing and existing.get("provider"):
            providers.add(existing["provider"])

        if new.get("provider"):
            providers.add(new["provider"])

        flat["_providers"] = sorted(p for p in providers if p)

        flat["_record"] = pub.to_dict()

        return flat
