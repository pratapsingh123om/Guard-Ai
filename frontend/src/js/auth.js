import { createClient } from '@supabase/supabase-js';

import { getAuthConfig } from './api.js';

let client = null;

export async function initializeAuth(onSessionChange) {
    const config = await getAuthConfig();
    if (!config.configured) return { configured: false, session: null };

    client = createClient(config.supabase_url, config.supabase_publishable_key, {
        auth: {
            flowType: 'pkce',
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true,
        },
    });
    client.auth.onAuthStateChange((_event, session) => {
        queueMicrotask(() => onSessionChange(session));
    });
    const { data, error } = await client.auth.getSession();
    if (error) throw error;
    return { configured: true, session: data.session };
}

export async function signInWithGoogle() {
    if (!client) throw new Error('Supabase authentication is not configured.');
    const { error } = await client.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: window.location.origin },
    });
    if (error) throw error;
}

export async function signInAsGuest() {
    if (!client) throw new Error('Supabase authentication is not configured.');
    const { data, error } = await client.auth.signInAnonymously();
    if (error) throw error;
    return data.session;
}

export async function signOut() {
    if (!client) return;
    const { error } = await client.auth.signOut();
    if (error) throw error;
}
