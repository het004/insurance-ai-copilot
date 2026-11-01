/** The app is the insurer's own assistant. Set the insurer's name here (and INSURER_NAME / INSURER_SHORT in backend/.env so the AI and documents match). */
export const INSURER_NAME = process.env.NEXT_PUBLIC_INSURER_NAME || "Al Rajhi Takaful";
export const INSURER_SHORT = process.env.NEXT_PUBLIC_INSURER_SHORT || "Al Rajhi Takaful";
/** The assistant's own name, like a bank's chatbot (أمان = "safety, peace of mind"). */
export const ASSISTANT_NAME = process.env.NEXT_PUBLIC_ASSISTANT_NAME || "Amaan";
export const ASSISTANT_NAME_AR = process.env.NEXT_PUBLIC_ASSISTANT_NAME_AR || "أمان";
export const INSURER_NAME_AR = process.env.NEXT_PUBLIC_INSURER_NAME_AR || "تكافل الراجحي";
export const LOGO_SRC = process.env.NEXT_PUBLIC_LOGO_SRC || "/brand/logo-mark.png";
