declare module "next/headers" {
  type CookieValue = { value: string } | undefined;
  type CookieStore = { get(name: string): CookieValue };
  export function cookies(): CookieStore;
}
