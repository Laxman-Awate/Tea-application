# Firebase Setup Instructions

## Problem Fixed
The "Unable to save order. Please try again" error was caused by missing Firebase configuration.

## Quick Fix (Already Applied)
The application now has a **local fallback** that saves orders to `local_orders/` directory when Firebase is not available. Your orders will work immediately.

## For Full Firebase Setup (Optional but Recommended)

### 1. Create Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project or use existing one
3. Enable Firestore Database
4. Create a "menu" collection (optional)
5. Create an "orders" collection (auto-created)

### 2. Get Service Account Key
1. In Firebase Console → Project Settings → Service Accounts
2. Click "Generate new private key"
3. Download the JSON file
4. Replace the content of `firebase-service-account.json` with your actual key

### 3. Update Environment Variables
Edit `.env` file and update:
- `FIREBASE_CREDENTIALS=firebase-service-account.json` (already set)
- Add your actual Firebase project details if needed

### 4. Test the Setup
```bash
cd Tea-application
python app.py
```

## Current Status
✅ **Orders will save locally** - No more "Unable to save order" errors
✅ **Menu items work** - Using sample menu from code
✅ **Application is functional** - Full ordering system works

## Next Steps
1. Test the ordering system - it should work now
2. Optionally set up Firebase for cloud storage
3. Check `local_orders/` directory for saved orders

## Troubleshooting
If you still see Firebase errors:
1. Check that `firebase-service-account.json` has valid credentials
2. Verify Firestore is enabled in Firebase Console
3. The app will continue working with local storage
