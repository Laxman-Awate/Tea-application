import { initializeApp } from "https://www.gstatic.com/firebasejs/9.23.0/firebase-app.js";
import { getMessaging, getToken } from "https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging.js";

// 🔥 Your Firebase project config
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

// Called when admin clicks button
window.enablePush = async function () {
  const permission = await Notification.requestPermission();

  if (permission !== "granted") {
    alert("Notification permission denied ❌");
    return;
  }

  const token = await getToken(messaging, {
    vapidKey: "BBnaEG3Z1vnWepXbLoRVLkCNXyy7pFyikb3G70gS3bcYOaUTGPPhom8S6byAP18NZmvl7jdFD37gyogTHRHDWaA"
  });

  if (!token) {
    alert("Token not generated");
    return;
  }

  console.log("🔥 ADMIN TOKEN:", token);

  // Send token to backend
  await fetch("/admin/save_fcm_token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token })
  });

  alert("✅ Notifications enabled");
};
