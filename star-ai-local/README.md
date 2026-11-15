# STAR AI على Windows

1. شغّل تطبيق Ollama وتأكد من وجود النموذج عبر `ollama list`. حمّل النموذج عند الحاجة عبر `ollama pull qwen3:1.7b`.
2. من مجلد `star-ai-local` شغّل `py -3 -X utf8 .\star_ai_web.py`.
3. افتح [صفحة وكيل AI Stayl](https://agent-ai-stayl.abdulstarzeki001.workers.dev/agent.html) على نفس الجهاز واكتب مثلاً «افتح المفكرة».

تدعم واجهة المتصفح الكتابة وقراءة الردود من اليمين لليسار. المحادثة تتصل بـ Ollama على الجهاز، وتُحفظ المحادثات والسجلات محلياً. طلبات فتح التطبيقات أو فحص Kali تعرض طلب موافقة داخل الواجهة المحلية. يلزم وجود توزيع `kali-linux` لاستخدام زر فحص Kali.

## نشر الموقع

اختر **GitHub Actions** في **Settings → Pages → Build and deployment**. ينشر سير عمل Pages ملفات الواجهة من `ai-stayl-app`. بعد الدمج يمكن تشغيله يدوياً من تبويب Actions.

واجهة وكيل البحث على Cloudflare تُنشر من حزمة Worker الحالية. شغّل `npm test` داخل `ai-stayl-app/backend`، ثم انشر `dist/agent-bundle.mjs` على Worker الحالي مع إعداداته الموجودة.
