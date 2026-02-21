import { useState, useEffect } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import {
  Shield,
  Lock,
  ArrowLeft,
  AlertCircle,
  Loader2,
  CheckCircle,
  Eye,
  EyeOff,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { ThemeToggle } from "../components/ui/ThemeToggle";
import { API_BASE_URL } from "../config/apiBase";

const API_BASE = API_BASE_URL;

type FormState = "idle" | "submitting" | "success" | "error" | "invalid_token";

// Password strength calculation
const calculatePasswordStrength = (
  password: string,
): { score: number; label: string; color: string } => {
  let score = 0;

  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^a-zA-Z0-9]/.test(password)) score += 1;

  if (score <= 2) return { score, label: "Weak", color: "bg-destructive" };
  if (score <= 4) return { score, label: "Medium", color: "bg-warning" };
  return { score, label: "Strong", color: "bg-success" };
};

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formState, setFormState] = useState<FormState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Check if token is present
  useEffect(() => {
    if (!token) {
      setFormState("invalid_token");
      setErrorMessage(
        "Invalid or missing reset token. Please request a new password reset.",
      );
    }
  }, [token]);

  const passwordStrength = calculatePasswordStrength(password);
  const passwordsMatch =
    password === confirmPassword && confirmPassword.length > 0;
  const isFormValid = password.length >= 8 && passwordsMatch && token;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isFormValid) return;

    setFormState("submitting");
    setErrorMessage(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/auth/password-reset/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            token,
            new_password: password,
          }),
        },
      );

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to reset password");
      }

      setFormState("success");

      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate("/login");
      }, 3000);
    } catch (err) {
      console.error("Password reset failed:", err);
      setFormState("error");
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Failed to reset password. The link may have expired.",
      );
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background relative">
      {/* Theme Toggle */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative animate-fade-in">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl gradient-brand mb-4 shadow-glow">
            <Shield className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">
            Create New Password
          </h1>
          <p className="text-muted-foreground">Enter your new password below</p>
        </div>

        <Card className="p-8">
          {formState === "success" ? (
            <div className="text-center" data-testid="success-message">
              <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-success" />
              </div>
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Password Reset Complete
              </h2>
              <p className="text-muted-foreground mb-6">
                Your password has been successfully reset. You'll be redirected
                to the login page shortly.
              </p>
              <Link to="/login">
                <Button variant="outline" className="w-full">
                  <ArrowLeft size={18} />
                  Go to Login
                </Button>
              </Link>
            </div>
          ) : formState === "invalid_token" ? (
            <div className="text-center" data-testid="invalid-token-message">
              <div className="w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertCircle className="w-8 h-8 text-destructive" />
              </div>
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Invalid Reset Link
              </h2>
              <p className="text-muted-foreground mb-6">{errorMessage}</p>
              <Link to="/forgot-password">
                <Button className="w-full mb-3">Request New Reset Link</Button>
              </Link>
              <Link to="/login">
                <Button variant="outline" className="w-full">
                  <ArrowLeft size={18} />
                  Back to Login
                </Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              {/* Error display */}
              {formState === "error" && errorMessage && (
                <div
                  className="mb-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm"
                  data-testid="error-message"
                >
                  <div className="flex items-center gap-3">
                    <AlertCircle size={18} />
                    <span>{errorMessage}</span>
                  </div>
                </div>
              )}

              <div className="space-y-5">
                {/* New Password */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      minLength={8}
                      disabled={formState === "submitting"}
                      className="pl-10 pr-10"
                      data-testid="password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>

                  {/* Password strength indicator */}
                  {password && (
                    <div className="mt-2" data-testid="password-strength">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full ${passwordStrength.color} transition-all duration-300`}
                            style={{
                              width: `${(passwordStrength.score / 6) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {passwordStrength.label}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        Use at least 8 characters with uppercase, lowercase,
                        numbers, and symbols
                      </p>
                    </div>
                  )}
                </div>

                {/* Confirm Password */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      type={showConfirmPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      disabled={formState === "submitting"}
                      className="pl-10 pr-10"
                      data-testid="confirm-password-input"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowConfirmPassword(!showConfirmPassword)
                      }
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showConfirmPassword ? (
                        <EyeOff size={18} />
                      ) : (
                        <Eye size={18} />
                      )}
                    </button>
                  </div>

                  {/* Match indicator */}
                  {confirmPassword && (
                    <div
                      className="mt-2 flex items-center gap-2"
                      data-testid="password-match"
                    >
                      {passwordsMatch ? (
                        <>
                          <CheckCircle size={14} className="text-success" />
                          <span className="text-xs text-success">
                            Passwords match
                          </span>
                        </>
                      ) : (
                        <>
                          <AlertCircle size={14} className="text-destructive" />
                          <span className="text-xs text-destructive">
                            Passwords do not match
                          </span>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <Button
                type="submit"
                disabled={formState === "submitting" || !isFormValid}
                className="mt-6 w-full"
                size="lg"
                data-testid="submit-button"
              >
                {formState === "submitting" ? (
                  <Loader2
                    className="w-5 h-5 animate-spin"
                    data-testid="spinner"
                  />
                ) : (
                  "Reset Password"
                )}
              </Button>

              <div className="mt-6 text-center">
                <Link
                  to="/login"
                  className="text-sm text-primary hover:underline inline-flex items-center gap-1"
                  data-testid="back-to-login"
                >
                  <ArrowLeft size={14} />
                  Back to Login
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
