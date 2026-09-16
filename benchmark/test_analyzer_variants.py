# Paraphrase groups: every prompt in a group should land in the same band.
VARIANTS = {
 "low": [
  ["Explain what HTML is", "What is HTML?", "Can you tell me what HTML is", "Explain HTML to a beginner"],
  ["Explain the difference between frontend and backend", "How is frontend different from backend?",
   "What's the difference between frontend and backend development?", "frontend vs backend, explained simply"],
  ["What is a database?", "Could you please tell me what a database actually is", "Define database"],
  ["Explain machine learning in simple terms", "What is machine learning, in plain English?", "Describe machine learning briefly"],
 ],
 "medium": [
  ["Write Python code for JWT authentication API", "Implement JWT auth for a Python API",
   "Can you write me a login API using JWTs in Python?", "I need a Flask endpoint that issues and verifies JWT tokens"],
  ["Explain how Docker containers work with examples", "How do Docker containers work? Give examples",
   "Walk me through how Docker containers work, with a couple of examples"],
  ["Debug a Python application and suggest improvements", "Fix bugs in my Python script and suggest improvements",
   "My Python app keeps crashing, help me debug it"],
  ["Explain how to deploy a Flask application on cloud infrastructure", "How do I deploy a Flask app to the cloud?",
   "Steps to deploy a Flask application on cloud infrastructure"],
  ["Build a recommendation system architecture for a small application",
   "Build a simple recommendation system for a small app",
   "Sketch the architecture of a recommendation engine for a small side project"],
 ],
 "high": [
  ["Design scalable architecture for AI SaaS platform",  # app.py demo button
   "Design a scalable AI SaaS platform architecture supporting millions of users",
   "Architect an AI SaaS platform that scales to millions of users",
   "How would you build an AI SaaS product that serves millions of users reliably?"],
  ["Compare RAG, fine-tuning, and agent-based architectures for an enterprise AI platform",
   "RAG vs fine-tuning vs agents for a large enterprise: weigh the tradeoffs",
   "Should an enterprise use RAG, fine tuning or agents? Compare the tradeoffs"],
  ["Analyze how an enterprise can reduce LLM inference costs while maintaining response quality",
   "How can an enterprise cut LLM inference spend without hurting answer quality?"],
  ["Design a production AI inference gateway with model locality optimization and fault-tolerant routing",
   "Build a router that sends each LLM request to the cheapest capable model, with fallback when a provider fails"],
 ],
}