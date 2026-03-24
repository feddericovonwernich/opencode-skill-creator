import unittest

from scripts.opencode_runtime import (
    OpenCodeMalformedOutputError,
    parse_opencode_json_output,
)


class ParseOpencodeJsonOutputTests(unittest.TestCase):
    def test_accepts_ndjson_events(self) -> None:
        output = '{"type": "start", "id": 1}\n{"type": "done", "id": 1}\n'

        parsed = parse_opencode_json_output(output)

        self.assertEqual(
            parsed,
            [
                {"type": "start", "id": 1},
                {"type": "done", "id": 1},
            ],
        )

    def test_accepts_single_json_object_payload(self) -> None:
        output = '  {"type": "final", "ok": true}  '

        parsed = parse_opencode_json_output(output)

        self.assertEqual(parsed, [{"type": "final", "ok": True}])

    def test_rejects_malformed_output(self) -> None:
        with self.assertRaises(OpenCodeMalformedOutputError):
            parse_opencode_json_output("not valid json")


if __name__ == "__main__":
    unittest.main()
