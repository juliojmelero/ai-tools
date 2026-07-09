from collections import OrderedDict


class Deduplicator:

    def deduplicate(self, publications):

        unique = OrderedDict()

        for p in publications:

            doi = p.get("doi") if isinstance(p, dict) else getattr(p, "doi", None)
            title = p.get("title") if isinstance(p, dict) else getattr(p, "title", "")

            if doi:
                key = "doi:" + doi.lower().strip()
            else:
                key = "title:" + title.lower().strip()

            if key not in unique:
                unique[key] = p
                continue

            current = unique[key]

            p_citations = p.get("citations") if isinstance(p, dict) else getattr(p, "citations", 0)
            c_citations = current.get("citations") if isinstance(current, dict) else getattr(current, "citations", 0)

            if (p_citations or 0) > (c_citations or 0):
                unique[key] = p

        return list(unique.values())
