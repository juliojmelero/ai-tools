import re


class QueryPlanner:

    def plan(self, query: str, provider: str) -> str:

        if provider == "scopus":
            return self._scopus(query)

        if provider == "ieee":
            return self._ieee(query)

        return query

    def _tokenize(self, text):
        words = re.findall(r"[A-Za-z0-9]+", text)
        return [w for w in words if len(w) > 2]

    def _scopus(self, query):

        words = self._tokenize(query)

        return "TITLE-ABS-KEY(" + " AND ".join(words) + ")"

    def _ieee(self, query):

        words = self._tokenize(query)

        return " AND ".join(words)
