import os
import subprocess
import sys
from flask import Flask
from threading import Thread
import telebot

# ১. ফ্ল্যাস্ক ওয়েব সার্ভার (হোস্ট বট অনলাইনে রাখার জন্য)
app = Flask('')

@app.route('/')
def home():
    return "Host Bot is Online and Active!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ২. মূল হোস্ট বটের টোকেন এবং ইউজার আইডি
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_HOST_BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# আপনার নিজের টেলিগ্রাম ইউজার আইডি এখানে দিন (নিরাপত্তার জন্য অত্যন্ত জরুরি)
OWNER_ID = 123456789  # <--- আপনার আইডি এখানে লিখুন

# চলমান সাব-বটের প্রসেস ট্র্যাক করার ভ্যারিয়েবল
deployed_process = None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 স্বাগতম! এটি আপনার নিজস্ব বট হোস্টিং সিস্টেম।\n\n"
        "**কীভাবে ব্যবহার করবেন:**\n"
        "১. আপনার তৈরি করা বটের `app.py` এবং `requirements.txt` ফাইল দুটি এখানে পাঠান।\n"
        "২. ফাইল পাঠানো হলে সেটি রান করতে লিখুন: `/deploy`\n"
        "৩. চলমান বটটি বন্ধ করতে লিখুন: `/stop`\n"
        "৪. বটের বর্তমান অবস্থা দেখতে লিখুন: `/status`"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# ফাইল রিসিভ করার হ্যান্ডলার
@bot.message_handler(content_types=['document'])
def save_files(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "দুঃখিত, আপনি এই হোস্টের মালিক নন।")
        return

    document = message.document
    file_name = document.file_name

    # শুধুমাত্র নির্দিষ্ট নামের ফাইল গ্রহণ করা হবে
    if file_name in ['app.py', 'requirements.txt']:
        bot.reply_to(message, f"📥 `{file_name}` ফাইলটি ডাউনলোড হচ্ছে...")
        try:
            file_info = bot.get_file(document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # সার্ভার ডিরেক্টরিতে ফাইলটি সেভ করা
            with open(file_name, 'wb') as f:
                f.write(downloaded_file)
            
            bot.reply_to(message, f"✅ `{file_name}` সফলভাবে সেভ করা হয়েছে।")
        except Exception as e:
            bot.reply_to(message, f"❌ ফাইল সেভ করতে সমস্যা হয়েছে: {str(e)}")
    else:
        bot.reply_to(message, "⚠️ অনুগ্রহ করে শুধু `app.py` অথবা `requirements.txt` ফাইল পাঠান। অন্য কোনো নামের ফাইল এখানে গ্রহণযোগ্য নয়।")

# কোড ডেপ্লয় এবং রান করার হ্যান্ডলার
@bot.message_handler(commands=['deploy'])
def deploy_bot(message):
    global deployed_process
    if message.from_user.id != OWNER_ID:
        return

    if not os.path.exists('app.py'):
        bot.reply_to(message, "❌ আপনি এখনও কোনো `app.py` ফাইল আপলোড করেননি।")
        return

    # আগের কোনো বট চালু থাকলে সেটি বন্ধ করা
    if deployed_process and deployed_process.poll() is None:
        bot.reply_to(message, "⚠️ একটি বট অলরেডি রান করছে! নতুন করে ডেপ্লয় করতে প্রথমে `/stop` লিখুন।", parse_mode="Markdown")
        return

    bot.reply_to(message, "⚙️ ডেপ্লয়মেন্ট প্রসেস শুরু হচ্ছে...")

    # ১. requirements.txt থাকলে প্যাকেজগুলো ব্যাকগ্রাউন্ডে ইনস্টল করা
    if os.path.exists('requirements.txt'):
        bot.reply_to(message, "📦 লাইব্রেরিগুলো ইন্সটল করা হচ্ছে (pip install)...")
        try:
            install_res = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                capture_output=True,
                text=True,
                timeout=90
            )
            if install_res.returncode != 0:
                bot.reply_to(message, f"⚠️ লাইব্রেরি ইন্সটল করতে সমস্যা হয়েছে:\n```\n{install_res.stderr}\n```", parse_mode="Markdown")
            else:
                bot.reply_to(message, "✅ লাইব্রেরিগুলো সফলভাবে ইন্সটল হয়েছে।")
        except Exception as e:
            bot.reply_to(message, f"❌ ইন্সটলেশন ত্রুটি: {str(e)}")

    # ২. সাব-বটটি রান করা (background process হিসেবে)
    bot.reply_to(message, "🚀 আপনার বটটি চালু করা হচ্ছে...")
    try:
        deployed_process = subprocess.Popen(
            [sys.executable, 'app.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        bot.reply_to(message, "🎉 অভিনন্দন! আপনার বটটি সফলভাবে ব্যাকগ্রাউন্ডে চালু হয়েছে।")
    except Exception as e:
        bot.reply_to(message, f"❌ বট রান করতে ব্যর্থ হয়েছে: {str(e)}")

# চলমান বট বন্ধ করার হ্যান্ডলার
@bot.message_handler(commands=['stop'])
def stop_bot(message):
    global deployed_process
    if message.from_user.id != OWNER_ID:
        return

    if deployed_process and deployed_process.poll() is None:
        deployed_process.terminate()  # চলমান প্রসেস বন্ধ করা
        deployed_process.wait()       # প্রসেস মেমোরি থেকে সম্পূর্ণ খালি করা
        deployed_process = None
        bot.reply_to(message, "🛑 আপনার বটটি সফলভাবে বন্ধ করা হয়েছে।")
    else:
        bot.reply_to(message, "ℹ️ বর্তমানে কোনো বট রান করছে না।")

# বটের স্ট্যাটাস দেখার হ্যান্ডলার
@bot.message_handler(commands=['status'])
def get_status(message):
    global deployed_process
    if message.from_user.id != OWNER_ID:
        return

    if deployed_process and deployed_process.poll() is None:
        bot.reply_to(message, "🟢 অবস্থা: আপনার বটটি বর্তমানে সচল আছে (Running)।")
    else:
        bot.reply_to(message, "🔴 অবস্থা: কোনো বট বর্তমানে চালু নেই (Stopped)।")

if __name__ == "__main__":
    # ওয়েব সার্ভার আলাদা থ্রেডে চালানো হচ্ছে
    server_thread = Thread(target=run_web_server)
    server_thread.start()
    
    print("Host Bot is running...")
    bot.infinity_polling()