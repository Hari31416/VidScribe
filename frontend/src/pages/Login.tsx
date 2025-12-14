import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { ModeToggle } from "../components/mode-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { FileVideo, Loader2 } from "lucide-react";

export function Login() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            const formData = new FormData();
            formData.append("username", username);
            formData.append("password", password);

            const response = await api.post("/auth/login", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });

            await login(response.data.access_token);
            navigate("/");
        } catch (err: any) {
            console.error("Login failed:", err);
            setError(
                err.response?.data?.detail || "Login failed. Please check your credentials."
            );
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container relative min-h-screen flex items-center justify-center">
            <div className="absolute right-4 top-4 md:right-8 md:top-8 z-20">
                <ModeToggle />
            </div>

            <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
                <div className="flex flex-col space-y-2 text-center">
                    <div className="flex justify-center mb-4">
                        <div className="flex items-center text-lg font-medium">
                            <FileVideo className="mr-2 h-6 w-6" />
                            VidScribe
                        </div>
                    </div>
                    <h1 className="text-2xl font-semibold tracking-tight">
                        Welcome back
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        Enter your credentials to sign in to your account
                    </p>
                </div>

                <div className="grid gap-6">
                    <form onSubmit={handleSubmit}>
                        <div className="grid gap-4">
                            <div className="grid gap-2">
                                <Label htmlFor="username">Username</Label>
                                <Input
                                    id="username"
                                    placeholder="Enter your username"
                                    type="text"
                                    autoCapitalize="none"
                                    autoComplete="username"
                                    autoCorrect="off"
                                    disabled={loading}
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="grid gap-2">
                                <Label htmlFor="password">Password</Label>
                                <Input
                                    id="password"
                                    placeholder="Enter your password"
                                    type="password"
                                    autoComplete="current-password"
                                    disabled={loading}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                            </div>

                            {error && (
                                <div className="text-sm font-medium text-destructive text-center">
                                    {error}
                                </div>
                            )}

                            <Button disabled={loading} type="submit">
                                {loading && (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                )}
                                Sign In
                            </Button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
