import unittest

from hammett import g
from hammett.impl import build_feedback_for_exception


def strip_colors(s):
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', s)


class RaiseTests(unittest.TestCase):
    def test_feedback_for_exception(self):
        g.reset()
        g.quiet = True

        # noinspection PyUnusedLocal
        def raises_exception():
            local_5 = 5
            local_foo = 'foo'
            raise Exception('foo')

        try:
            raises_exception()
        except Exception:
            output = build_feedback_for_exception()

        assert strip_colors(output) == """--- Local variables ---
local_5:
    5
local_foo:
    'foo'""", repr(output)

    def test_assert_feedback(self):
        g.reset()
        g.quiet = True

        # noinspection PyUnusedLocal
        def raises_assertion():
            local_5 = 5
            local_foo = 'foo'
            assert 5 == 6

        try:
            raises_assertion()
        except AssertionError:
            output = build_feedback_for_exception()

        assert strip_colors(output) == """--- Local variables ---
local_5:
    5
local_foo:
    'foo'

--- Assert components ---
left:
    5
right:
    6""", repr(output)

    def test_multi_line_assert(self):
        g.reset()
        g.quiet = True

        # noinspection PyUnusedLocal
        def raises_assertion():
            local_5 = 5
            local_foo = 'foo'
            assert (
                5 == 6
            )

        try:
            raises_assertion()
        except AssertionError:
            output = build_feedback_for_exception()

        assert strip_colors(output) == """--- Local variables ---
local_5:
    5
local_foo:
    'foo'

--- Assert components ---
left:
    5
right:
    6""", repr(output)

    def test_multi_big_variables(self):
        g.reset()
        g.quiet = True
        # noinspection SpellCheckingInspection

        sample = """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
        Vestibulum posuere tristique orci eget tempor. 
        Phasellus interdum posuere massa tristique imperdiet.
        Phasellus luctus nibh id congue suscipit.
        Fusce et sapien pretium, pretium nisl vel, sollicitudin augue.
        Donec sagittis orci nec fringilla auctor.
        Etiam dictum imperdiet gravida.
        Integer sagittis mattis libero pretium pulvinar.
        Nullam aliquet congue faucibus.
        Aenean ex dolor, aliquet at malesuada quis, varius et velit.
        Donec sed arcu mauris. Maecenas quis vulputate dolor.
        Suspendisse non elementum odio. 
        Suspendisse hendrerit quam vitae arcu porta aliquet.
        Etiam molestie accumsan pulvinar. 
        Curabitur porttitor eleifend sem auctor sagittis. 
        """
        # noinspection SpellCheckingInspection
        sample_corrupt = sample.replace('mattis libero', 'FOO!')

        # noinspection PyUnusedLocal
        def raises_assertion():
            assert sample == sample_corrupt

        try:
            raises_assertion()
        except AssertionError:
            output = build_feedback_for_exception()

        expected = f"""--- Local variables ---
sample:
    {sample!r}
sample_corrupt:
    {sample_corrupt!r}

--- Assert components ---
left:
    {sample!r}
right:
    {sample_corrupt!r}

--- Diff of left and right assert components ---
--- expected
+++ actual
@@ -6,7 +6,7 @@
         Fusce et sapien pretium, pretium nisl vel, sollicitudin augue.
         Donec sagittis orci nec fringilla auctor.
         Etiam dictum imperdiet gravida.
-        Integer sagittis mattis libero pretium pulvinar.
+        Integer sagittis FOO! pretium pulvinar.
         Nullam aliquet congue faucibus.
         Aenean ex dolor, aliquet at malesuada quis, varius et velit.
         Donec sed arcu mauris. Maecenas quis vulputate dolor."""
        assert strip_colors(output) == expected, repr(output)
