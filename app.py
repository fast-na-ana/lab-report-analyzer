from groq import Groq

# 1. Plug in your Groq API key (it usually starts with gsk_)
client = Groq(
    api_key="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",
)

try:
    print("Connecting to Groq LPU...")
    chat_completion = client.chat.completions.create(
        # Llama 3 is excellent for Case Study 6 (Lab Analysis)
        messages=[
            {
                "role": "user",
                "content": "Test: Say 'Groq Connection Successful'!",
            }
        ],
        model="llama-3.3-70b-versatile",
    )

    print("\n--- RESPONSE RECEIVED ---")
    print(chat_completion.choices[0].message.content)
    print("-------------------------\n")
    print("Success! Your Groq key is working.")

except Exception as e:
    print(f"Error: {e}")