from datetime import datetime


class Ranker:

    def score(self, publication):
        title = (publication.get("title") or "").lower()
        citations = publication.get("citations") or 0
        year = publication.get("year") or 0

        current_year = datetime.utcnow().year
        age = max(1, current_year - year + 1) if year else 20

        relevance_score = 0.0

        if "dynamic line rating" in title:
            relevance_score = 1.0
        elif "line rating" in title:
            relevance_score = 0.75
        elif "ampacity" in title:
            relevance_score = 0.6
        elif "transmission line" in title:
            relevance_score = 0.4

        citations_per_year = citations / age
        impact_score = min(citations_per_year, 30) / 30

        if year:
            recency_score = max(0.0, 1.0 - ((current_year - year) / 15))
        else:
            recency_score = 0.0

        score = (
            0.55 * relevance_score
            + 0.30 * impact_score
            + 0.15 * recency_score
        )

        publication["score"] = round(score, 4)
        publication["citations_per_year"] = round(citations_per_year, 2)

        return publication["score"]

    def rank(self, publications, sort_mode="score"):
        for p in publications:
            self.score(p)

        if sort_mode == "none":
            return publications

        if sort_mode == "citations":
            return sorted(
                publications,
                key=lambda p: p.get("citations") or 0,
                reverse=True,
            )

        if sort_mode == "year_desc":
            return sorted(
                publications,
                key=lambda p: p.get("year") or 0,
                reverse=True,
            )

        if sort_mode == "year_asc":
            return sorted(
                publications,
                key=lambda p: p.get("year") or 9999,
            )

        if sort_mode == "title":
            return sorted(
                publications,
                key=lambda p: (p.get("title") or "").lower(),
            )

        if sort_mode == "provider":
            return sorted(
                publications,
                key=lambda p: (p.get("provider") or "").lower(),
            )

        return sorted(
            publications,
            key=lambda p: p.get("score", 0),
            reverse=True,
        )
