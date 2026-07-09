class MergeStrategies:

    @staticmethod
    def first_non_empty(old, new):

        if old in (None, "", [], {}):
            return new

        return old


    @staticmethod
    def longest(old, new):

        old = old or ""
        new = new or ""

        if len(new) > len(old):
            return new

        return old


    @staticmethod
    def maximum(old, new):

        return max(
            old or 0,
            new or 0,
        )


    @staticmethod
    def union(old, new):

        result = []

        for x in old or []:
            if x not in result:
                result.append(x)

        for x in new or []:
            if x not in result:
                result.append(x)

        return result


    @staticmethod
    def overwrite(old, new):

        if new is None:
            return old

        return new


STRATEGIES = {

    "first_non_empty": MergeStrategies.first_non_empty,

    "longest": MergeStrategies.longest,

    "maximum": MergeStrategies.maximum,

    "union": MergeStrategies.union,

    "overwrite": MergeStrategies.overwrite,

}
