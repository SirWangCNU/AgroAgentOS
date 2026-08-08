import { useState, forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface FloatingInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "className"> {
  label: string;
  icon?: LucideIcon;
  error?: string;
  isPassword?: boolean;
}

const FloatingInput = forwardRef<HTMLInputElement, FloatingInputProps>(
  ({ label, icon: Icon, error, isPassword = false, type = "text", id, ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);
    const [focused, setFocused] = useState(false);
    const hasValue = props.value !== undefined && props.value !== "";
    const isActive = focused || hasValue;

    const inputType = isPassword ? (showPassword ? "text" : "password") : type;
    const inputId = id || label.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="relative">
        <div
          className={`
            relative flex items-center rounded-xl border transition-all duration-200 bg-white
            ${error
              ? "border-red-400 shadow-[0_0_0_3px_rgba(239,68,68,0.1)] animate-shake"
              : isActive
                ? "border-green-500 shadow-[0_0_0_3px_rgba(22,163,74,0.12)]"
                : "border-slate-200 hover:border-slate-300"
            }
          `}
        >
          {/* 左侧图标 */}
          {Icon && (
            <div className={`pl-4 pr-2 transition-colors duration-200 ${isActive ? "text-green-600" : "text-slate-400"}`}>
              <Icon className="w-5 h-5" />
            </div>
          )}

          {/* 输入框和标签容器 */}
          <div className="relative flex-1">
            <input
              ref={ref}
              id={inputId}
              type={inputType}
              className={`
                w-full bg-transparent outline-none text-slate-700 placeholder-transparent
                transition-all duration-200
                ${isActive ? "pt-5 pb-2" : "py-3.5"}
                ${Icon ? "pr-3" : "px-4 pr-3"}
                ${isPassword ? "pr-12" : ""}
              `}
              placeholder={label}
              onFocus={(e) => {
                setFocused(true);
                props.onFocus?.(e);
              }}
              onBlur={(e) => {
                setFocused(false);
                props.onBlur?.(e);
              }}
              {...props}
            />
            <label
              htmlFor={inputId}
              className={`
                absolute left-0 transition-all duration-200 pointer-events-none
                ${Icon ? "left-0" : "left-4"}
                ${isActive
                  ? "top-1.5 text-xs font-medium text-green-600"
                  : `top-1/2 -translate-y-1/2 text-sm ${error ? "text-red-400" : "text-slate-400"}`
                }
              `}
            >
              {label}
            </label>
          </div>

          {/* 密码显示/隐藏按钮 */}
          {isPassword && (
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowPassword(!showPassword)}
              className={`pr-4 pl-2 transition-colors duration-200 ${focused || showPassword ? "text-green-600" : "text-slate-400"} hover:text-green-600`}
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          )}
        </div>

        {/* 错误提示 */}
        {error && (
          <p className="mt-1.5 text-xs text-red-500 flex items-center gap-1">
            {error}
          </p>
        )}
      </div>
    );
  }
);

FloatingInput.displayName = "FloatingInput";

export default FloatingInput;
