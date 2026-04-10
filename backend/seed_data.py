import urllib.request
import json

tickets = [
    {
        "customer_name": "Alice Smith",
        "customer_email": "alice@example.com",
        "subject": "Missing items in order",
        "description": "I ordered 3 laptops but only 2 arrived in the package. Please help me get the refund for the missing one or send it out.",
        "language": "en",
        "source_channel": "email"
    },
    {
        "customer_name": "Bob Jones",
        "customer_email": "bob.jones@example.org",
        "subject": "System crash on login",
        "description": "Whenever I try to log into the portal using my credentials, the whole app crashes with a 500 server error.",
        "language": "en",
        "source_channel": "web"
    },
    {
        "customer_name": "Charlie Brown",
        "customer_email": "charlie@peanuts.com",
        "subject": "Cancel my subscription",
        "description": "Please cancel my monthly premium subscription immediately. I don't use the service anymore.",
        "language": "en",
        "source_channel": "app"
    },
    {
        "customer_name": "Diana Prince",
        "customer_email": "diana@themiscyra.net",
        "subject": "Billing error on last invoice",
        "description": "My last invoice was charged twice. I see two identical charges on my credit card statement from yesterday.",
        "language": "en",
        "source_channel": "email"
    },
    {
        "customer_name": "Edward Kenway",
        "customer_email": "edward@pirates.com",
        "subject": "How do I update my profile?",
        "description": "I just want to know how to change my shipping address. The UI is confusing and I can't find the settings.",
        "language": "en",
        "source_channel": "web"
    }
]

url = "http://localhost:8000/api/tickets/route"
headers = {'Content-Type': 'application/json'}

for ticket in tickets:
    req = urllib.request.Request(url, data=json.dumps(ticket).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"Created ticket #{result['ticket_id']}: {result['ticket_id']} - {result['routing']['assigned_queue']}")
    except Exception as e:
        print(f"Error creating ticket: {e}")
