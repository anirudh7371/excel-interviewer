import os
import google.generativeai as genai
from groq import Groq
import requests
import aiohttp

class FreeAIService:
    """Unified wrapper for multiple free/cheap AI providers."""

    def __init__(self, provider="gemini"):
        self.provider = provider.lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.hf_key = os.getenv("HUGGINGFACE_API_KEY")

        # Initialize provider clients if keys are present
        if self.provider == "gemini" and self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        elif self.provider == "groq" and self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)
        elif self.provider == "huggingface" and self.hf_key:
            self.hf_headers = {"Authorization": f"Bearer {self.hf_key}"}
        elif self.provider == "ollama":
            self.ollama_url = "http://localhost:11434/api/generate"
        else:
            print(f"[FreeAIService] No valid API key configured for provider: {self.provider}")

    async def _make_ai_call(self, prompt: str) -> str:
        """Dispatch call to the chosen AI provider and return raw text."""
        if self.provider == "gemini" and self.gemini_key:
            try:
                response = await self.gemini_model.generate_content_async(prompt)
                return response.text
            except Exception as e:
                print(f"[Gemini] Error: {e}")
                return None

        elif self.provider == "groq" and self.groq_key:
            try:
                completion = self.groq_client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}]
                )
                return completion.choices[0].message.content
            except Exception as e:
                print(f"[Groq] Error: {e}")
                return None

        elif self.provider == "huggingface" and self.hf_key:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium",
                        headers=self.hf_headers,
                        json={"inputs": prompt}
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            if isinstance(result, list) and "generated_text" in result[0]:
                                return result[0]["generated_text"]
            except Exception as e:
                print(f"[HuggingFace] Error: {e}")
                return None

        elif self.provider == "ollama":
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.ollama_url,
                        json={"model": "llama2", "prompt": prompt}
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            return result.get("response", None)
            except Exception as e:
                print(f"[Ollama] Error: {e}")
                return None

        return None
