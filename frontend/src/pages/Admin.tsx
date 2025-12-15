import React, { useState, useEffect } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

interface User {
    username: string;
    email: string;
    full_name: string;
    disabled: boolean;
    role: string;
}

export function Admin() {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const { user: currentUser } = useAuth();

    // Form state
    const [newUser, setNewUser] = useState({
        username: "",
        password: "",
        email: "",
        full_name: "",
        role: "user"
    });

    const fetchUsers = async () => {
        try {
            const response = await api.get("/auth/users");
            setUsers(response.data);
        } catch (err) {
            console.error("Failed to fetch users:", err);
            setError("Failed to load users");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await api.post("/auth/users", newUser);
            setNewUser({
                username: "",
                password: "",
                email: "",
                full_name: "",
                role: "user"
            });
            fetchUsers();
        } catch (err: any) {
            console.error("Failed to create user:", err);
            setError(err.response?.data?.detail || "Failed to create user");
        }
    };

    const handleDeleteUser = async (username: string) => {
        if (!confirm(`Are you sure you want to delete user ${username}?`)) return;

        try {
            await api.delete(`/auth/users/${username}`);
            fetchUsers();
        } catch (err: any) {
            console.error("Failed to delete user:", err);
            setError(err.response?.data?.detail || "Failed to delete user");
        }
    };

    if (loading) return <div className="p-8">Loading...</div>;

    return (
        <div className="container mx-auto px-4 py-8">
            <h1 className="text-3xl font-bold mb-8">User Management</h1>

            {error && (
                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
                    {error}
                </div>
            )}

            {/* Create User Form */}
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6 mb-8">
                <h2 className="text-xl font-semibold mb-4">Create Not User</h2>
                <form onSubmit={handleCreateUser} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium mb-1">Username</label>
                            <input
                                type="text"
                                required
                                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                                value={newUser.username}
                                onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Password</label>
                            <input
                                type="password"
                                required
                                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                                value={newUser.password}
                                onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Email</label>
                            <input
                                type="email"
                                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                                value={newUser.email}
                                onChange={e => setNewUser({ ...newUser, email: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Full Name</label>
                            <input
                                type="text"
                                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                                value={newUser.full_name}
                                onChange={e => setNewUser({ ...newUser, full_name: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Role</label>
                            <select
                                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                                value={newUser.role}
                                onChange={e => setNewUser({ ...newUser, role: e.target.value })}
                            >
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                    </div>
                    <button
                        type="submit"
                        className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
                    >
                        Create User
                    </button>
                </form>
            </div>

            {/* Users List */}
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-900">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Full Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {users.map(user => (
                            <tr key={user.username}>
                                <td className="px-6 py-4 whitespace-nowrap">{user.username}</td>
                                <td className="px-6 py-4 whitespace-nowrap">{user.full_name}</td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${user.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-green-100 text-green-800'
                                        }`}>
                                        {user.role}
                                    </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    {user.disabled ? (
                                        <span className="text-red-600">Disabled</span>
                                    ) : (
                                        <span className="text-green-600">Active</span>
                                    )}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                    {user.username !== currentUser?.username && (
                                        <button
                                            onClick={() => handleDeleteUser(user.username)}
                                            className="text-red-600 hover:text-red-900"
                                        >
                                            Delete
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
