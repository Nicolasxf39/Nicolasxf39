import os
import base64
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
import asyncio

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'calorie_tracker_database')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Pydantic models
class UserProfile(BaseModel):
    user_id: str
    name: str
    age: int
    gender: str  # "male" or "female"
    height: float  # in cm
    weight: float  # in kg
    activity_level: str  # "sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"
    goal_weight: float  # in kg
    daily_calorie_target: Optional[float] = None
    created_at: Optional[datetime] = None

class FoodAnalysisRequest(BaseModel):
    image_base64: str
    user_id: str

class CalorieEntry(BaseModel):
    entry_id: str
    user_id: str
    food_name: str
    calories: float
    meal_type: str  # "breakfast", "lunch", "dinner", "snack"
    image_base64: Optional[str] = None
    timestamp: datetime
    confidence: Optional[float] = None

class DailyIntakeResponse(BaseModel):
    date: str
    total_calories: float
    target_calories: float
    entries: List[CalorieEntry]
    remaining_calories: float

def calculate_daily_calories(age: int, gender: str, height: float, weight: float, activity_level: str, goal_weight: float) -> float:
    """Calculate daily calorie needs using Harris-Benedict equation with activity multiplier"""
    # Base Metabolic Rate (BMR) calculation
    if gender.lower() == "male":
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:  # female
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)
    
    # Activity level multipliers
    activity_multipliers = {
        "sedentary": 1.2,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.9
    }
    
    # Total Daily Energy Expenditure (TDEE)
    tdee = bmr * activity_multipliers.get(activity_level, 1.375)
    
    # Adjust for weight goal
    if goal_weight < weight:  # Weight loss
        deficit = min(500, (weight - goal_weight) * 50)  # Max 500 cal deficit per day
        return max(1200, tdee - deficit)  # Minimum 1200 calories
    elif goal_weight > weight:  # Weight gain
        surplus = min(500, (goal_weight - weight) * 50)  # Max 500 cal surplus per day
        return tdee + surplus
    else:  # Maintenance
        return tdee

async def analyze_food_with_ai(image_base64: str) -> dict:
    """Analyze food image using OpenAI GPT-4o"""
    try:
        # Initialize LLM chat
        chat = LlmChat(
            api_key=OPENAI_API_KEY,
            session_id=f"food_analysis_{uuid.uuid4()}",
            system_message="""You are a nutrition expert. Analyze the food image and provide a detailed JSON response with the following structure:
            {
                "food_items": [
                    {
                        "name": "food name",
                        "portion_size": "estimated portion size",
                        "calories": number,
                        "confidence": number (0.0 to 1.0)
                    }
                ],
                "total_calories": number,
                "analysis_confidence": number (0.0 to 1.0),
                "notes": "any additional observations"
            }
            
            Be as accurate as possible with calorie estimates. If you're unsure about a food item, indicate lower confidence. Consider portion sizes carefully."""
        ).with_model("openai", "gpt-4o")
        
        # Create image content
        image_content = ImageContent(image_base64=image_base64)
        
        # Send message with image
        user_message = UserMessage(
            text="Please analyze this food image and provide detailed nutritional information in the requested JSON format.",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        
        # Try to parse JSON from response
        import json
        try:
            # Extract JSON from response if it's wrapped in markdown or other text
            response_text = str(response)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_str = response_text[json_start:json_end]
            else:
                json_str = response_text
            
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "food_items": [{"name": "Unknown food", "portion_size": "1 serving", "calories": 200, "confidence": 0.3}],
                "total_calories": 200,
                "analysis_confidence": 0.3,
                "notes": f"Analysis text: {response}"
            }
        
    except Exception as e:
        print(f"Error in AI analysis: {str(e)}")
        return {
            "food_items": [{"name": "Unknown food", "portion_size": "1 serving", "calories": 200, "confidence": 0.2}],
            "total_calories": 200,
            "analysis_confidence": 0.2,
            "notes": f"Error occurred: {str(e)}"
        }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Calorie Tracker API is running"}

@app.post("/api/profile")
async def create_or_update_profile(profile: UserProfile):
    """Create or update user profile"""
    profile.created_at = datetime.now(timezone.utc)
    
    # Calculate daily calorie target
    profile.daily_calorie_target = calculate_daily_calories(
        profile.age, profile.gender, profile.height, 
        profile.weight, profile.activity_level, profile.goal_weight
    )
    
    # Convert to dict for MongoDB
    profile_dict = profile.dict()
    
    # Update or insert profile
    await db.profiles.update_one(
        {"user_id": profile.user_id},
        {"$set": profile_dict},
        upsert=True
    )
    
    return {"message": "Profile saved successfully", "daily_calorie_target": profile.daily_calorie_target}

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str):
    """Get user profile"""
    profile = await db.profiles.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Remove MongoDB _id field
    profile.pop('_id', None)
    return profile

@app.post("/api/analyze-food")
async def analyze_food(request: FoodAnalysisRequest):
    """Analyze food image and return calorie information"""
    try:
        # Analyze image with AI
        analysis_result = await analyze_food_with_ai(request.image_base64)
        
        # Create calorie entry
        entry_id = str(uuid.uuid4())
        food_name = ", ".join([item["name"] for item in analysis_result.get("food_items", [])])
        total_calories = analysis_result.get("total_calories", 0)
        confidence = analysis_result.get("analysis_confidence", 0.5)
        
        # Store in database
        calorie_entry = {
            "entry_id": entry_id,
            "user_id": request.user_id,
            "food_name": food_name,
            "calories": total_calories,
            "meal_type": "unspecified",
            "image_base64": request.image_base64,
            "timestamp": datetime.now(timezone.utc),
            "confidence": confidence,
            "analysis_details": analysis_result
        }
        
        await db.calorie_entries.insert_one(calorie_entry)
        
        return {
            "entry_id": entry_id,
            "food_name": food_name,
            "calories": total_calories,
            "confidence": confidence,
            "analysis_details": analysis_result,
            "message": "Food analyzed successfully"
        }
        
    except Exception as e:
        print(f"Error analyzing food: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing food: {str(e)}")

@app.put("/api/entry/{entry_id}/meal-type")
async def update_meal_type(entry_id: str, meal_type: str):
    """Update meal type for a calorie entry"""
    valid_meal_types = ["breakfast", "lunch", "dinner", "snack"]
    if meal_type not in valid_meal_types:
        raise HTTPException(status_code=400, detail="Invalid meal type")
    
    result = await db.calorie_entries.update_one(
        {"entry_id": entry_id},
        {"$set": {"meal_type": meal_type}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {"message": "Meal type updated successfully"}

@app.get("/api/daily-intake/{user_id}")
async def get_daily_intake(user_id: str, date: Optional[str] = None):
    """Get daily calorie intake for a user"""
    if date:
        try:
            target_date = datetime.fromisoformat(date).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        target_date = datetime.now(timezone.utc).date()
    
    # Get user profile for calorie target
    profile = await db.profiles.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    # Get entries for the date
    start_date = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_date = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    cursor = db.calorie_entries.find({
        "user_id": user_id,
        "timestamp": {"$gte": start_date, "$lte": end_date}
    }).sort("timestamp", 1)
    
    entries = []
    total_calories = 0.0
    
    async for entry in cursor:
        entry.pop('_id', None)  # Remove MongoDB _id
        entries.append(entry)
        total_calories += entry.get("calories", 0)
    
    target_calories = profile.get("daily_calorie_target", 2000)
    remaining_calories = max(0, target_calories - total_calories)
    
    return {
        "date": target_date.isoformat(),
        "total_calories": total_calories,
        "target_calories": target_calories,
        "entries": entries,
        "remaining_calories": remaining_calories
    }

@app.delete("/api/entry/{entry_id}")
async def delete_entry(entry_id: str):
    """Delete a calorie entry"""
    result = await db.calorie_entries.delete_one({"entry_id": entry_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {"message": "Entry deleted successfully"}

@app.get("/api/history/{user_id}")
async def get_history(user_id: str, days: int = 7):
    """Get calorie intake history for the last N days"""
    profile = await db.profiles.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)
    
    # Aggregate daily totals
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$timestamp"
                    }
                },
                "total_calories": {"$sum": "$calories"},
                "entry_count": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    cursor = db.calorie_entries.aggregate(pipeline)
    history = []
    target_calories = profile.get("daily_calorie_target", 2000)
    
    async for day in cursor:
        history.append({
            "date": day["_id"],
            "total_calories": day["total_calories"],
            "target_calories": target_calories,
            "entry_count": day["entry_count"],
            "percentage_of_target": (day["total_calories"] / target_calories) * 100
        })
    
    return {
        "history": history,
        "target_calories": target_calories,
        "period_days": days
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)