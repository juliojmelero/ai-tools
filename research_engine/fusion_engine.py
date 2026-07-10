from research_models.publication import Publication
from research_engine.provider_priorities import FIELD_RULES
from research_engine.provider_result import extract_provider_metadata


class FusionEngine:

    def _dict_to_publication(self, data):
        if "_record" in data:
            if "_schema_version" not in data:
                # Cached canonical records written before schema versioning
                # contain the V1 record body but no explicit envelope version.
                data = {"_schema_version": 1, "_record": data["_record"]}
            return Publication.from_dict(data)

        pub = Publication()

        metadata = extract_provider_metadata(data)

        for field in FIELD_RULES:
            if field in data:
                pub.add(
                    field_name=field,
                    value=data.get(field),
                    **metadata,
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

            metadata = extract_provider_metadata(new)

            for field in FIELD_RULES:
                if field in new:
                    pub.add(
                        field_name=field,
                        value=new.get(field),
                        **metadata,
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

        flat.update(pub.to_dict())

        return flat
