"""Shared Ogma Print toolkit.

Everything in here is product-agnostic: it must not import the dog bowl, a lamp,
a spinner or a clicker. Products depend on `ogma`; `ogma` depends on nothing but
third-party libraries.

Destined for `shared/ogma/` in the monorepo restructure. It lives under
`backend/generator/` for now only because that directory is already on sys.path
for every generator, which keeps this seam cut to a one-line import change per
module instead of a path rewrite.
"""
