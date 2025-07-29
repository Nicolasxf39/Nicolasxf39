#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Calorie Counting App
Tests all endpoints with realistic data and validates OpenAI integration
"""

import requests
import json
import base64
import uuid
from datetime import datetime, timezone
import os
import sys

# Get backend URL from frontend .env file
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading frontend .env: {e}")
        return None

BASE_URL = get_backend_url()
if not BASE_URL:
    print("ERROR: Could not get backend URL from frontend/.env")
    sys.exit(1)

API_BASE = f"{BASE_URL}/api"

# Test data
TEST_USER_ID = str(uuid.uuid4())
TEST_PROFILE = {
    "user_id": TEST_USER_ID,
    "name": "John Smith",
    "age": 25,
    "gender": "male",
    "height": 175.0,
    "weight": 70.0,
    "activity_level": "moderately_active",
    "goal_weight": 65.0
}

# Sample base64 encoded image (small PNG image for testing)
SAMPLE_IMAGE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

class TestResults:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        
    def add_result(self, test_name, passed, message="", details=None):
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "status": status,
            "message": message,
            "details": details
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status}: {test_name} - {message}")
        
    def print_summary(self):
        print("\n" + "="*60)
        print("BACKEND API TEST SUMMARY")
        print("="*60)
        for result in self.results:
            print(f"{result['status']}: {result['test']}")
            if result['message']:
                print(f"    {result['message']}")
        print(f"\nTotal: {self.passed + self.failed} | Passed: {self.passed} | Failed: {self.failed}")
        print("="*60)

def test_health_endpoint(test_results):
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                test_results.add_result("Health Check", True, "API is healthy")
            else:
                test_results.add_result("Health Check", False, f"Unexpected response: {data}")
        else:
            test_results.add_result("Health Check", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Health Check", False, f"Exception: {str(e)}")

def test_profile_creation(test_results):
    """Test profile creation and calorie calculation"""
    try:
        response = requests.post(f"{API_BASE}/profile", json=TEST_PROFILE, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "daily_calorie_target" in data:
                # Verify Harris-Benedict calculation for male, 25, 175cm, 70kg, moderately_active
                expected_bmr = 88.362 + (13.397 * 70) + (4.799 * 175) - (5.677 * 25)
                expected_tdee = expected_bmr * 1.55  # moderately_active multiplier
                expected_calories = max(1200, expected_tdee - 250)  # weight loss adjustment
                
                actual_calories = data["daily_calorie_target"]
                if abs(actual_calories - expected_calories) < 50:  # Allow 50 cal tolerance
                    test_results.add_result("Profile Creation", True, 
                                          f"Profile created with calorie target: {actual_calories}")
                else:
                    test_results.add_result("Profile Creation", False, 
                                          f"Calorie calculation incorrect. Expected ~{expected_calories}, got {actual_calories}")
            else:
                test_results.add_result("Profile Creation", False, "Missing daily_calorie_target in response")
        else:
            test_results.add_result("Profile Creation", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Profile Creation", False, f"Exception: {str(e)}")

def test_profile_retrieval(test_results):
    """Test profile retrieval"""
    try:
        response = requests.get(f"{API_BASE}/profile/{TEST_USER_ID}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("user_id") == TEST_USER_ID and data.get("name") == "John Smith":
                test_results.add_result("Profile Retrieval", True, "Profile retrieved successfully")
                return data
            else:
                test_results.add_result("Profile Retrieval", False, "Profile data mismatch")
        else:
            test_results.add_result("Profile Retrieval", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Profile Retrieval", False, f"Exception: {str(e)}")
    return None

def test_food_analysis(test_results):
    """Test the critical OpenAI food analysis endpoint"""
    try:
        request_data = {
            "image_base64": SAMPLE_IMAGE_BASE64,
            "user_id": TEST_USER_ID
        }
        response = requests.post(f"{API_BASE}/analyze-food", json=request_data, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["entry_id", "food_name", "calories", "confidence", "analysis_details"]
            
            missing_fields = [field for field in required_fields if field not in data]
            if not missing_fields:
                # Verify data types and ranges
                if (isinstance(data["calories"], (int, float)) and 
                    isinstance(data["confidence"], (int, float)) and 
                    0 <= data["confidence"] <= 1 and
                    data["calories"] >= 0):
                    test_results.add_result("OpenAI Food Analysis", True, 
                                          f"Food analyzed: {data['food_name']}, {data['calories']} calories, confidence: {data['confidence']}")
                    return data["entry_id"]
                else:
                    test_results.add_result("OpenAI Food Analysis", False, "Invalid data types or ranges")
            else:
                test_results.add_result("OpenAI Food Analysis", False, f"Missing fields: {missing_fields}")
        else:
            test_results.add_result("OpenAI Food Analysis", False, f"Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        test_results.add_result("OpenAI Food Analysis", False, f"Exception: {str(e)}")
    return None

def test_meal_type_update(test_results, entry_id):
    """Test updating meal type for an entry"""
    if not entry_id:
        test_results.add_result("Meal Type Update", False, "No entry_id available")
        return
        
    try:
        # Test with valid meal type
        response = requests.put(f"{API_BASE}/entry/{entry_id}/meal-type", 
                              params={"meal_type": "breakfast"}, timeout=10)
        if response.status_code == 200:
            test_results.add_result("Meal Type Update", True, "Meal type updated to breakfast")
        else:
            test_results.add_result("Meal Type Update", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Meal Type Update", False, f"Exception: {str(e)}")

def test_daily_intake(test_results):
    """Test daily intake retrieval"""
    try:
        response = requests.get(f"{API_BASE}/daily-intake/{TEST_USER_ID}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_fields = ["date", "total_calories", "target_calories", "entries", "remaining_calories"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                test_results.add_result("Daily Intake", True, 
                                      f"Daily intake: {data['total_calories']}/{data['target_calories']} calories")
            else:
                test_results.add_result("Daily Intake", False, f"Missing fields: {missing_fields}")
        else:
            test_results.add_result("Daily Intake", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Daily Intake", False, f"Exception: {str(e)}")

def test_history(test_results):
    """Test calorie history retrieval"""
    try:
        response = requests.get(f"{API_BASE}/history/{TEST_USER_ID}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "history" in data and "target_calories" in data:
                test_results.add_result("Calorie History", True, 
                                      f"History retrieved with {len(data['history'])} days")
            else:
                test_results.add_result("Calorie History", False, "Missing required fields in response")
        else:
            test_results.add_result("Calorie History", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Calorie History", False, f"Exception: {str(e)}")

def test_entry_deletion(test_results, entry_id):
    """Test deleting a calorie entry"""
    if not entry_id:
        test_results.add_result("Entry Deletion", False, "No entry_id available")
        return
        
    try:
        response = requests.delete(f"{API_BASE}/entry/{entry_id}", timeout=10)
        if response.status_code == 200:
            test_results.add_result("Entry Deletion", True, "Entry deleted successfully")
        else:
            test_results.add_result("Entry Deletion", False, f"Status code: {response.status_code}")
    except Exception as e:
        test_results.add_result("Entry Deletion", False, f"Exception: {str(e)}")

def test_error_handling(test_results):
    """Test error handling for invalid requests"""
    try:
        # Test invalid user profile retrieval
        response = requests.get(f"{API_BASE}/profile/invalid-user-id", timeout=10)
        if response.status_code == 404:
            test_results.add_result("Error Handling - Invalid Profile", True, "404 returned for invalid user")
        else:
            test_results.add_result("Error Handling - Invalid Profile", False, f"Expected 404, got {response.status_code}")
            
        # Test invalid meal type
        response = requests.put(f"{API_BASE}/entry/test-entry/meal-type", 
                              params={"meal_type": "invalid_meal"}, timeout=10)
        if response.status_code in [400, 404]:  # Either bad request or not found is acceptable
            test_results.add_result("Error Handling - Invalid Meal Type", True, f"{response.status_code} returned for invalid meal type")
        else:
            test_results.add_result("Error Handling - Invalid Meal Type", False, f"Expected 400/404, got {response.status_code}")
            
    except Exception as e:
        test_results.add_result("Error Handling", False, f"Exception: {str(e)}")

def main():
    print("Starting Comprehensive Backend API Tests")
    print(f"Testing against: {API_BASE}")
    print("="*60)
    
    test_results = TestResults()
    
    # Run tests in priority order
    print("\n1. Testing Health Check...")
    test_health_endpoint(test_results)
    
    print("\n2. Testing Profile Management...")
    test_profile_creation(test_results)
    profile_data = test_profile_retrieval(test_results)
    
    print("\n3. Testing OpenAI Food Analysis (CRITICAL)...")
    entry_id = test_food_analysis(test_results)
    
    print("\n4. Testing Entry Management...")
    test_meal_type_update(test_results, entry_id)
    
    print("\n5. Testing Data Retrieval...")
    test_daily_intake(test_results)
    test_history(test_results)
    
    print("\n6. Testing Entry Deletion...")
    test_entry_deletion(test_results, entry_id)
    
    print("\n7. Testing Error Handling...")
    test_error_handling(test_results)
    
    # Print final summary
    test_results.print_summary()
    
    # Return exit code based on results
    return 0 if test_results.failed == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)