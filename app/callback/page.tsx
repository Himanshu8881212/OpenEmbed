"use client";
import { useEffect, useState } from "react";
import { completeLogin } from "@/lib/web/session";
import { ErrorBox, Loading } from "@/lib/web/ui";

export default function Callback() {
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { completeLogin(new URLSearchParams(location.search)).then((back) => location.replace(back), setError); }, []);
  return <main id="main">{error ? <><ErrorBox error={error} /><a href="/">Back</a></> : <Loading what="Completing sign-in" />}</main>;
}
