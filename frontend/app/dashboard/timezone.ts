"use client";

import { createContext, useContext } from "react";

export const TimezoneContext = createContext<string>("UTC");
export const useClinicTz = () => useContext(TimezoneContext);
