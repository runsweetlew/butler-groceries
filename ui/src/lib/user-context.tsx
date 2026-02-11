'use client';

import { createContext, useContext } from 'react';

interface UserContextType {
  currentUser: any | null;
  setCurrentUser: (user: any) => void;
  users: any[];
}

export const UserContext = createContext<UserContextType>({
  currentUser: null,
  setCurrentUser: () => {},
  users: [],
});

export function useUser() {
  return useContext(UserContext);
}
