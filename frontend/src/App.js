import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  // States
  const [currentView, setCurrentView] = useState('dashboard');
  const [userProfile, setUserProfile] = useState(null);
  const [dailyIntake, setDailyIntake] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [showCamera, setShowCamera] = useState(false);
  const [capturedImage, setCapturedImage] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Camera refs
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  
  // User ID (in a real app, this would come from authentication)
  const [userId] = useState('user_' + Date.now().toString());

  // Initialize user profile
  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    try {
      setLoading(true);
      // Try to load existing profile
      const profileResponse = await axios.get(`${BACKEND_URL}/api/profile/${userId}`);
      setUserProfile(profileResponse.data);
      
      // Load daily intake
      const intakeResponse = await axios.get(`${BACKEND_URL}/api/daily-intake/${userId}`);
      setDailyIntake(intakeResponse.data);
    } catch (error) {
      console.log('No existing profile found, will create new one');
    } finally {
      setLoading(false);
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: 'environment' }, 
        audio: false 
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setShowCamera(true);
    } catch (error) {
      console.error('Error accessing camera:', error);
      alert('Error accessing camera. Please ensure camera permissions are granted.');
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setShowCamera(false);
    setCapturedImage(null);
  };

  const capturePhoto = () => {
    if (videoRef.current && canvasRef.current) {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0);
      
      // Convert to base64
      const imageData = canvas.toDataURL('image/jpeg', 0.8);
      const base64Data = imageData.split(',')[1];
      
      setCapturedImage(imageData);
      return base64Data;
    }
    return null;
  };

  const analyzeFood = async () => {
    const base64Image = capturePhoto();
    if (!base64Image) {
      alert('Failed to capture image');
      return;
    }

    setIsAnalyzing(true);
    stopCamera();

    try {
      const response = await axios.post(`${BACKEND_URL}/api/analyze-food`, {
        image_base64: base64Image,
        user_id: userId
      });

      setAnalysisResult(response.data);
      
      // Refresh daily intake
      const intakeResponse = await axios.get(`${BACKEND_URL}/api/daily-intake/${userId}`);
      setDailyIntake(intakeResponse.data);
      
      setCurrentView('analysis');
    } catch (error) {
      console.error('Error analyzing food:', error);
      alert('Error analyzing food: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const updateMealType = async (entryId, mealType) => {
    try {
      await axios.put(`${BACKEND_URL}/api/entry/${entryId}/meal-type?meal_type=${mealType}`);
      
      // Refresh daily intake
      const intakeResponse = await axios.get(`${BACKEND_URL}/api/daily-intake/${userId}`);
      setDailyIntake(intakeResponse.data);
      
      alert('Meal type updated successfully!');
    } catch (error) {
      console.error('Error updating meal type:', error);
      alert('Error updating meal type');
    }
  };

  const deleteEntry = async (entryId) => {
    if (!window.confirm('Are you sure you want to delete this entry?')) return;
    
    try {
      await axios.delete(`${BACKEND_URL}/api/entry/${entryId}`);
      
      // Refresh daily intake
      const intakeResponse = await axios.get(`${BACKEND_URL}/api/daily-intake/${userId}`);
      setDailyIntake(intakeResponse.data);
      
      alert('Entry deleted successfully!');
      setCurrentView('dashboard');
    } catch (error) {
      console.error('Error deleting entry:', error);
      alert('Error deleting entry');
    }
  };

  const saveProfile = async (profileData) => {
    try {
      setLoading(true);
      const response = await axios.post(`${BACKEND_URL}/api/profile`, {
        ...profileData,
        user_id: userId
      });
      
      setUserProfile({ ...profileData, user_id: userId, daily_calorie_target: response.data.daily_calorie_target });
      
      // Load daily intake after profile creation
      const intakeResponse = await axios.get(`${BACKEND_URL}/api/daily-intake/${userId}`);
      setDailyIntake(intakeResponse.data);
      
      setCurrentView('dashboard');
      alert('Profile saved successfully!');
    } catch (error) {
      console.error('Error saving profile:', error);
      alert('Error saving profile');
    } finally {
      setLoading(false);
    }
  };

  const ProfileForm = () => {
    const [formData, setFormData] = useState({
      name: userProfile?.name || '',
      age: userProfile?.age || '',
      gender: userProfile?.gender || '',
      height: userProfile?.height || '',
      weight: userProfile?.weight || '',
      activity_level: userProfile?.activity_level || '',
      goal_weight: userProfile?.goal_weight || ''
    });

    const handleSubmit = (e) => {
      e.preventDefault();
      saveProfile({
        ...formData,
        age: parseInt(formData.age),
        height: parseFloat(formData.height),
        weight: parseFloat(formData.weight),
        goal_weight: parseFloat(formData.goal_weight)
      });
    };

    return (
      <div className="profile-form-container">
        <div className="profile-card">
          <h2 className="heading-2">Your Profile</h2>
          <p className="body-medium text-secondary">Tell us about yourself to get personalized calorie recommendations</p>
          
          <form onSubmit={handleSubmit} className="profile-form">
            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                type="text"
                className="form-input"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Age</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.age}
                  onChange={(e) => setFormData({...formData, age: e.target.value})}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Gender</label>
                <select
                  className="form-input"
                  value={formData.gender}
                  onChange={(e) => setFormData({...formData, gender: e.target.value})}
                  required
                >
                  <option value="">Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Height (cm)</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.height}
                  onChange={(e) => setFormData({...formData, height: e.target.value})}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Weight (kg)</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.weight}
                  onChange={(e) => setFormData({...formData, weight: e.target.value})}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Goal Weight (kg)</label>
              <input
                type="number"
                className="form-input"
                value={formData.goal_weight}
                onChange={(e) => setFormData({...formData, goal_weight: e.target.value})}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Activity Level</label>
              <select
                className="form-input"
                value={formData.activity_level}
                onChange={(e) => setFormData({...formData, activity_level: e.target.value})}
                required
              >
                <option value="">Select activity level</option>
                <option value="sedentary">Sedentary (little/no exercise)</option>
                <option value="lightly_active">Lightly Active (light exercise 1-3 days/week)</option>
                <option value="moderately_active">Moderately Active (moderate exercise 3-5 days/week)</option>
                <option value="very_active">Very Active (hard exercise 6-7 days/week)</option>
                <option value="extra_active">Extra Active (very hard exercise, physical job)</option>
              </select>
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Saving...' : 'Save Profile'}
            </button>
          </form>
        </div>
      </div>
    );
  };

  const Dashboard = () => {
    if (!userProfile) {
      return (
        <div className="welcome-container">
          <div className="welcome-card">
            <h1 className="heading-1">Welcome to CalorieTracker</h1>
            <p className="body-large">Start your health journey by creating your profile</p>
            <button 
              className="btn-primary"
              onClick={() => setCurrentView('profile')}
            >
              Create Profile
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="dashboard-container">
        <div className="dashboard-header">
          <h1 className="heading-2">Hello, {userProfile.name}!</h1>
          <p className="body-medium text-secondary">Track your daily calorie intake</p>
        </div>

        {dailyIntake && (
          <div className="calorie-overview">
            <div className="calorie-card">
              <div className="calorie-circle">
                <div className="calorie-number">
                  <span className="heading-1">{Math.round(dailyIntake.total_calories)}</span>
                  <span className="body-small text-secondary">/{Math.round(dailyIntake.target_calories)}</span>
                </div>
                <p className="body-small text-secondary">calories today</p>
              </div>
              
              <div className="calorie-progress">
                <div 
                  className="calorie-progress-bar"
                  style={{
                    width: `${Math.min(100, (dailyIntake.total_calories / dailyIntake.target_calories) * 100)}%`
                  }}
                ></div>
              </div>
              
              <p className="body-medium">
                {dailyIntake.remaining_calories > 0 
                  ? `${Math.round(dailyIntake.remaining_calories)} calories remaining`
                  : `${Math.round(Math.abs(dailyIntake.remaining_calories))} calories over target`
                }
              </p>
            </div>
          </div>
        )}

        <div className="action-buttons">
          <button 
            className="btn-primary scan-button"
            onClick={startCamera}
          >
            📷 Scan Food
          </button>
        </div>

        {dailyIntake && dailyIntake.entries.length > 0 && (
          <div className="food-entries">
            <h3 className="heading-3">Today's Meals</h3>
            <div className="entries-list">
              {dailyIntake.entries.map((entry) => (
                <div key={entry.entry_id} className="food-entry-card">
                  <div className="entry-content">
                    <div className="entry-details">
                      <h4 className="body-medium">{entry.food_name}</h4>
                      <p className="body-small text-secondary">
                        {Math.round(entry.calories)} calories • {entry.meal_type}
                      </p>
                      <p className="caption text-muted">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                    <div className="entry-actions">
                      <select
                        className="meal-type-select"
                        value={entry.meal_type}
                        onChange={(e) => updateMealType(entry.entry_id, e.target.value)}
                      >
                        <option value="breakfast">Breakfast</option>
                        <option value="lunch">Lunch</option>
                        <option value="dinner">Dinner</option>
                        <option value="snack">Snack</option>
                        <option value="unspecified">Unspecified</option>
                      </select>
                      <button
                        className="delete-button"
                        onClick={() => deleteEntry(entry.entry_id)}
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                  {entry.image_base64 && (
                    <img 
                      src={`data:image/jpeg;base64,${entry.image_base64}`}
                      alt="Food"
                      className="entry-image"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const CameraView = () => (
    <div className="camera-container">
      <div className="camera-header">
        <h2 className="heading-3">Scan Your Food</h2>
        <button className="close-button" onClick={stopCamera}>✕</button>
      </div>
      
      <div className="camera-view">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          className="camera-video"
          style={{ display: showCamera ? 'block' : 'none' }}
        />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        
        {capturedImage && (
          <img src={capturedImage} alt="Captured food" className="captured-image" />
        )}
      </div>
      
      <div className="camera-controls">
        {showCamera && !capturedImage && (
          <button 
            className="btn-primary capture-button"
            onClick={capturePhoto}
          >
            📸 Capture
          </button>
        )}
        
        {capturedImage && (
          <div className="capture-actions">
            <button 
              className="btn-secondary"
              onClick={() => {
                setCapturedImage(null);
                startCamera();
              }}
            >
              Retake
            </button>
            <button 
              className="btn-primary"
              onClick={analyzeFood}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze Food'}
            </button>
          </div>
        )}
      </div>
    </div>
  );

  const AnalysisView = () => (
    <div className="analysis-container">
      <div className="analysis-header">
        <h2 className="heading-2">Food Analysis</h2>
        <button 
          className="close-button" 
          onClick={() => setCurrentView('dashboard')}
        >
          ✕
        </button>
      </div>
      
      {analysisResult && (
        <div className="analysis-result">
          <div className="analysis-image">
            <img 
              src={capturedImage} 
              alt="Analyzed food" 
              className="analyzed-food-image"
            />
          </div>
          
          <div className="analysis-details">
            <div className="calorie-summary">
              <h3 className="heading-3">
                {Math.round(analysisResult.calories)} Calories
              </h3>
              <p className="body-medium text-secondary">
                Confidence: {Math.round(analysisResult.confidence * 100)}%
              </p>
            </div>
            
            <div className="food-details">
              <h4 className="heading-4">Detected Food:</h4>
              <p className="body-medium">{analysisResult.food_name}</p>
            </div>
            
            {analysisResult.analysis_details && (
              <div className="detailed-analysis">
                <h4 className="heading-4">Detailed Analysis:</h4>
                {analysisResult.analysis_details.food_items?.map((item, index) => (
                  <div key={index} className="food-item">
                    <p className="body-medium">{item.name}</p>
                    <p className="body-small text-secondary">
                      {item.portion_size} • {Math.round(item.calories)} calories
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          <div className="analysis-actions">
            <button 
              className="btn-secondary"
              onClick={() => {
                setAnalysisResult(null);
                startCamera();
              }}
            >
              Scan Another
            </button>
            <button 
              className="btn-primary"
              onClick={() => setCurrentView('dashboard')}
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );

  // Navigation
  const Navigation = () => (
    <nav className="navigation">
      <div className="nav-brand">
        <h1 className="heading-4">CalorieTracker</h1>
      </div>
      <div className="nav-links">
        <button 
          className={`nav-link ${currentView === 'dashboard' ? 'active' : ''}`}
          onClick={() => setCurrentView('dashboard')}
        >
          Dashboard
        </button>
        <button 
          className={`nav-link ${currentView === 'profile' ? 'active' : ''}`}
          onClick={() => setCurrentView('profile')}
        >
          Profile
        </button>
      </div>
    </nav>
  );

  return (
    <div className="app">
      <Navigation />
      
      <main className="main-content">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner"></div>
            <p>Loading...</p>
          </div>
        )}
        
        {currentView === 'dashboard' && <Dashboard />}
        {currentView === 'profile' && <ProfileForm />}
        {currentView === 'analysis' && <AnalysisView />}
        {showCamera && <CameraView />}
      </main>
    </div>
  );
}

export default App;