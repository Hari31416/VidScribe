import React, { createContext, useContext, useState, useEffect } from "react";
import { api } from "../api";

// Types
interface User {
    username: string;
    email: string | null;
    full_name: string | null;
    disabled: boolean;
    role: string;
}

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (token: string) => Promise<void>;
    logout: () => void;
    isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // Check for token on mount
    useEffect(() => {
        const checkAuth = async () => {
            const token = localStorage.getItem("token");
            if (token) {
                try {
                    // Verify token and get user details
                    const response = await api.get("/auth/me", {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                    setUser(response.data);
                } catch (error) {
                    console.error("Auth check failed:", error);
                    localStorage.removeItem("token");
                    setUser(null);
                }
            }
            setIsLoading(false);
        };

        checkAuth();
    }, []);

    const login = async (token: string) => {
        localStorage.setItem("token", token);
        try {
            const response = await api.get("/auth/me", {
                headers: { Authorization: `Bearer ${token}` }
            });
            setUser(response.data);
        } catch (error) {
            console.error("Get user failed:", error);
            throw error;
        }
    };

    const logout = () => {
        localStorage.removeItem("token");
        setUser(null);
    };

    const isAdmin = user?.role === "admin";

    return (
        <AuthContext.Provider value={{
            user,
            isAuthenticated: !!user,
            isLoading,
            login,
            logout,
            isAdmin
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
