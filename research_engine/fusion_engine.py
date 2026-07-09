from research_models.publication import Publication
from research_engine.provider_priorities import FIELD_RULES


class FusionEngine:

    def _dict_to_publication(self, data):
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
