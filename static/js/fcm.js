import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getMessaging, getToken } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging.js";

// 🔥 Firebase config (from Firebase Console)
const firebaseConfig = {
  apiKey: "AIzaSyBhg-9L1n5iKsOhvtmPwH8iSm-DWgkc2wg",
  authDomain: "tea-application-ac2c1.firebaseapp.com",
  projectId: "tea-application-ac2c1",
  storageBucket: "tea-application-ac2c1.firebasestorage.app",
  messagingSenderId: "260284245568",
  appId: "1:260284245568:web:b031fc17c5a6480663e1a5",
  measurementId: "G-EG6WN4TE02"
};

// Init Firebase
const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

// ✅ GLOBAL function (so button onclick can find it)
window.enablePush = async function () {
  try {
    // Service worker registration disabled
    // const reg = await navigator.serviceWorker.register("/firebase-messaging-sw.js");
    // console.log("✅ SW registered");

    // Get FCM token
    const token = await getToken(messaging, {
      vapidKey: "BBnaEG3Z1vnWepXbLoRVLkCNXyy7pFyikb3G70gS3bcYOaUTGPPhom8S6byAP18NZmvl7jdFD37gyogTHRHDWaA",
      serviceWorkerRegistration: reg
    });

    if (!token) {
      alert("❌ No token received");
      return;
    }

    console.log("🔥 FCM TOKEN:", token);

    // Send token to backend
    await fetch("/admin/save_token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token })
    });

    alert("✅ Push notifications enabled");

  } catch (err) {
    console.error("❌ Push error:", err);
    alert("Push failed. Check console.");
  }
};


