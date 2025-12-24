# Keep Stripe push provisioning classes
-keep class com.stripe.android.pushProvisioning.** { *; }
-dontwarn com.stripe.android.pushProvisioning.**

# Keep all Stripe SDK classes
-keep class com.stripe.android.** { *; }
-dontwarn com.stripe.android.**
