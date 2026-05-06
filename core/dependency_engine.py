class DependencyEngine:

    def __init__(self, dep_map):
        self.map = dep_map

    def cascade(self, milestone):
        impacted = []
        queue = [milestone]

        while queue:
            current = queue.pop(0)
            for d in self.map.get(current, []):
                impacted.append(d)
                queue.append(d)

        return impacted