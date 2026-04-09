// src/api.js
const API_BASE = "http://localhost:8000/api";

export const getHealth = async () => {
    try {
        const res = await fetch(`${API_BASE}/health`);
        return res.ok;
    } catch {
        return false;
    }
};

export const submitTicket = async (payload) => {
    const res = await fetch(`${API_BASE}/tickets/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to submit ticket");
    return await res.json();
};

export const getTickets = async () => {
    const res = await fetch(`${API_BASE}/tickets`);
    if (!res.ok) throw new Error("Failed to fetch tickets");
    return await res.json();
};
