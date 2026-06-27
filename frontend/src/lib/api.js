const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
export class ApiError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
        this.name = 'ApiError';
    }
}
async function request(path, init) {
    const response = await fetch(`${BASE_URL}${path}`, {
        headers: { 'content-type': 'application/json' },
        ...init,
    });
    if (!response.ok) {
        const body = (await response.json().catch(() => null));
        throw new ApiError(response.status, body?.detail ?? response.statusText);
    }
    return (await response.json());
}
export const api = {
    search(query, limit = 10) {
        return request(`/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    },
    getParcel(parcelNumber) {
        return request(`/parcels/${encodeURIComponent(parcelNumber)}`);
    },
    getVerdict(parcelNumber) {
        return request(`/parcels/${encodeURIComponent(parcelNumber)}/verdict`);
    },
    refreshVerdict(parcelNumber) {
        return request(`/parcels/${encodeURIComponent(parcelNumber)}/verdict/refresh`, {
            method: 'POST',
        });
    },
    getComps(parcelNumber) {
        return request(`/parcels/${encodeURIComponent(parcelNumber)}/comps`);
    },
    ask(parcelNumber, question) {
        return request(`/parcels/${encodeURIComponent(parcelNumber)}/ask`, {
            method: 'POST',
            body: JSON.stringify({ question }),
        });
    },
    getLayers() {
        return request('/layers');
    },
};
