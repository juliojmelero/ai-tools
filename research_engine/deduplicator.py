class Deduplicator:

    def cluster(self, publications) -> dict[str, list[dict]]:
        clusters = {}

        for p in publications:
            doi = p.get("doi") if isinstance(p, dict) else getattr(p, "doi", None)
            title = p.get("title") if isinstance(p, dict) else getattr(p, "title", "")

            if doi:
                key = "doi:" + doi.lower().strip()
            else:
                key = "title:" + title.lower().strip()

            clusters.setdefault(key, []).append(p)

        return clusters
