"""Dubles de banco usados pelos testes: registram o SQL executado e o commit."""


class FakeCursor:
    def __init__(self, statements, rowcount=1, row=None):
        self.statements = statements
        self.rowcount = rowcount
        self._row = row

    def execute(self, query, params=()):
        self.statements.append((" ".join(query.split()), tuple(params)))
        return self

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, rowcount=1, row=None):
        self.statements = []
        self.committed = False
        self._rowcount = rowcount
        self._row = row

    def cursor(self):
        return FakeCursor(self.statements, self._rowcount, self._row)

    def commit(self):
        self.committed = True

    def close(self):
        pass
