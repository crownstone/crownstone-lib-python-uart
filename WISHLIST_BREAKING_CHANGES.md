# Wishlist of breaking changes

There are always a lot of changes we would like to make, that would not be backwards compatible.
So in case we have to make a release that breaks the API, we can look at this list and implement them as well.

## The list
- Make all commands wait for the result. This means some have to become async.
- Remove asset filter functions from control handler.
