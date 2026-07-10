from collections import defaultdict

from research_engine.publication_identity import PublicationIdentityResolver


class Deduplicator:

    def __init__(self, identity_resolver=None):
        self.identity_resolver = identity_resolver or PublicationIdentityResolver()

    def cluster(self, publications) -> dict[str, list[dict]]:
        identified = [
            (publication, self.identity_resolver.resolve(publication))
            for publication in publications
        ]
        identified.sort(
            key=lambda item: self.identity_resolver.record_sort_key(item[0])
        )

        dois_by_title = defaultdict(set)
        for _, identity in identified:
            if identity.doi and identity.title:
                dois_by_title[identity.title].add(identity.doi)

        clusters = defaultdict(list)
        fallback_occurrences = defaultdict(int)
        for publication, identity in identified:
            if identity.doi:
                key = f"doi:{identity.doi}"
            elif identity.title:
                matching_dois = dois_by_title[identity.title]
                if len(matching_dois) == 1:
                    key = f"doi:{next(iter(matching_dois))}"
                else:
                    key = f"title:{identity.title}"
            else:
                sort_key = self.identity_resolver.record_sort_key(publication)
                occurrence = fallback_occurrences[sort_key]
                fallback_occurrences[sort_key] += 1
                key = self.identity_resolver.fallback_identity(
                    publication, occurrence
                )
            clusters[key].append(publication)

        return {key: clusters[key] for key in sorted(clusters)}
