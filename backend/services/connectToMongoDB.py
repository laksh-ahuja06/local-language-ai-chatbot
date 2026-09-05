import os

from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime

# Load variables from .env
load_dotenv()

# Get MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in .env")

# Create MongoDB client
client = MongoClient(MONGO_URI)

# Select database
db = client["medvoice"]

# Select collection
reminders_collection = db["reminders"]

def update_job_ids(reminder_id, job_ids):
    result = reminders_collection.update_one(
        {"_id": ObjectId(reminder_id)},
        {
            "$set": {
                "job_ids": job_ids
            }
        }
    )
    return result.modified_count == 1

def save_reminder(reminder):
    # Save a reminder document to MongoDB.
    reminder["status"] = "active"
    reminder["created_at"] = datetime.now()
    result = reminders_collection.insert_one(reminder)
    print("Reminder saved to MongoDB.")
    print("Reminder ID:", result.inserted_id)

    return str(result.inserted_id)

def get_reminders():
    reminders = list(reminders_collection.find())
    for reminder in reminders:
        reminder["_id"] = str(reminder["_id"])
    return reminders

def test_database_connection():
    try:
        client.admin.command("ping")
        print("MongoDB connected successfully!")

    except Exception as e:

        print("MongoDB connection failed:")
        print(e)

if __name__ == "__main__":
    test_database_connection()
    test_reminder = {
        "medicine": "paracetamol",
        "dose": "500 mg",
        "time": "9:00 PM",
        "frequency": "daily",
        "status": "active"
    }
    reminder_id = save_reminder(test_reminder)
    print("Saved reminder ID:", reminder_id)

def delete_reminder(reminder_id):
    result = reminders_collection.delete_one(
        {"_id": ObjectId(reminder_id)}
    )

    if result.deleted_count == 1:
        return True

    return False
