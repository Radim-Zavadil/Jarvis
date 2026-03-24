from dotenv import load_dotenv
load_dotenv()

import os, requests, json

QUERY = """
query {
  viewer {
    assignedIssues(
      filter: {
        and: [
          { state: { type: { neq: "completed" } } }
          { state: { type: { neq: "cancelled" } } }
        ]
      }
      orderBy: priority
    ) {
      nodes { title priority state { name } url }
    }
  }
}
"""

r = requests.post(
    "https://api.linear.app/graphql",
    json={"query": QUERY},
    headers={
        "Authorization": os.environ['LINEAR_API_KEY'],
        "Content-Type": "application/json",
    },
    timeout=15,
)
print("STATUS:", r.status_code)
print(json.dumps(r.json(), indent=2))
