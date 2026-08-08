interface PasswordStrengthProps {
  password: string;
}

function calculateStrength(password: string): { score: number; label: string; color: string } {
  if (!password) return { score: 0, label: "", color: "" };

  let score = 0;

  if (password.length >= 6) score++;
  if (password.length >= 10) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;

  if (score <= 1) return { score, label: "弱", color: "bg-red-400" };
  if (score <= 2) return { score, label: "较弱", color: "bg-orange-400" };
  if (score <= 3) return { score, label: "中等", color: "bg-amber-400" };
  if (score <= 4) return { score, label: "强", color: "bg-green-400" };
  return { score, label: "非常强", color: "bg-emerald-500" };
}

export default function PasswordStrength({ password }: PasswordStrengthProps) {
  const { score, label, color } = calculateStrength(password);

  if (!password) return null;

  return (
    <div className="mt-2">
      <div className="flex gap-1 mb-1">
        {[1, 2, 3, 4, 5].map((level) => (
          <div
            key={level}
            className={`h-1 flex-1 rounded-full transition-all duration-300 ${
              level <= score ? color : "bg-slate-200"
            }`}
          />
        ))}
      </div>
      <p className={`text-xs ${
        score <= 2 ? "text-red-500" : score <= 3 ? "text-amber-500" : "text-green-600"
      }`}>
        密码强度: {label}
      </p>
    </div>
  );
}
