"""Shared Ogma Print toolkit.

Everything in here is product-agnostic: it must not import the dog bowl, a lamp,
a spinner or a clicker. Products depend on `ogma`; `ogma` depends on nothing but
third-party libraries.

Every product generator puts `<repo>/shared` on sys.path in its header, so
`from ogma import ...` works from any product without installation.
"""
