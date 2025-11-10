"""Quick script to reproduce the check-job-alignment issue.

Run with:

    python manage.py shell -c "import scripts.debug_job_alignment as s; s.run(user_id=1348)"

Adjust the user_id/position as needed.
"""

import json
import requests


def run(user_id: int, position: str = "Sales Managers", from_autocomplete: bool = False):
    payload = {
        "position": position,
        "user_id": user_id,
        "from_autocomplete": from_autocomplete,
    }

    print("Payload:", json.dumps(payload, indent=2))

    response = requests.post(
        "http://127.0.0.1:8000/api/shared/check-job-alignment/",
        json=payload,
        timeout=10,
    )

    print("Status:", response.status_code)
    try:
        print("JSON:", json.dumps(response.json(), indent=2))
    except ValueError:
        print("Body:", response.text)


if __name__ == "__main__":
    run(user_id=1348)


