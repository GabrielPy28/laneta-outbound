export type LoginUser = {
  id: string;
  email: string;
  name: string;
  avatar_url: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: LoginUser;
};
