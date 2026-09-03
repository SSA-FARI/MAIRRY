export interface DemoUser {
  id: string;
  loginId: string;
  displayName: string;
  email: string | null;
}

export interface DemoSession {
  user: DemoUser;
  mode: "DEMO";
}
