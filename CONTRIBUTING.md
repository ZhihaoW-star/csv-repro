# Contributing

Small improvements backed by a concrete support workflow are welcome. Run `python3 -m unittest discover -s tests -v` before proposing a change. Keep the default workflow local and dependency-free.

Please use invented data in reports. Include Python version, OS, delimiter/encoding and positional options, expected behavior, observed behavior, and a tiny synthetic CSV. Never upload production files, private IDs, secrets or a source-value mapping. Test that the fixture actually reproduces the issue before posting it.

Useful next steps: a confirmed parser fixture that is currently rejected incorrectly; a better way to show transformation limits; a documented real support workflow; tests for platform-specific newline behavior. Discuss expanded formats or a web UI before adding dependencies.
