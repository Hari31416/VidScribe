import React from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, FileVideo, PlusCircle, Shield, LogOut } from "lucide-react";
import { cn } from "@/utils";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { ModeToggle } from "@/components/mode-toggle";

interface LayoutProps {
    children?: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAdmin, logout, user } = useAuth();

    const navItems = [
        { icon: LayoutDashboard, label: "Dashboard", href: "/" },
        { icon: PlusCircle, label: "New Project", href: "/new" },
    ];

    if (isAdmin) {
        navItems.push({ icon: Shield, label: "Admin", href: "/admin" });
    }

    const handleLogout = () => {
        logout();
        navigate("/login");
    };

    return (
        <div className="min-h-screen bg-background font-sans antialiased flex">
            {/* Sidebar */}
            <aside className="w-64 border-r bg-card hidden md:flex flex-col">
                <div className="p-6">
                    <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
                        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                            <FileVideo className="w-5 h-5 text-primary-foreground" />
                        </div>
                        VidScribe
                    </h1>
                </div>

                <nav className="flex-1 px-4 space-y-2">
                    {navItems.map((item) => (
                        <Link key={item.href} to={item.href}>
                            <Button
                                variant={location.pathname === item.href ? "secondary" : "ghost"}
                                className={cn(
                                    "w-full justify-start gap-2",
                                    location.pathname === item.href && "bg-secondary"
                                )}
                            >
                                <item.icon className="w-4 h-4" />
                                {item.label}
                            </Button>
                        </Link>
                    ))}
                </nav>

                <div className="p-4 border-t space-y-4">
                    <div className="flex items-center justify-between px-2">
                        <span className="text-sm font-medium truncate max-w-[120px]" title={user?.username}>
                            {user?.username}
                        </span>
                        <ModeToggle />
                    </div>

                    <Button
                        variant="ghost"
                        className="w-full justify-start gap-2 text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={handleLogout}
                    >
                        <LogOut className="w-4 h-4" />
                        Logout
                    </Button>

                    <p className="text-xs text-muted-foreground text-center">
                        v0.1.0 Beta
                    </p>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <div className="h-full">
                    {children || <Outlet />}
                </div>
            </main>
        </div>
    );
}
