# Pleroma instance configuration
import Config
config :pleroma, Pleroma.Web.Endpoint,
   url: [host: "asamblea.social", scheme: "https", port: 443],
   http: [ip: {127, 0, 0, 1}, port: 4000],
   secret_key_base: System.get_env("AKKOMA_SECRET_KEY_BASE"),
   live_view: [signing_salt: System.get_env("AKKOMA_LIVE_VIEW_SALT")],
   signing_salt: System.get_env("AKKOMA_SIGNING_SALT")
config :pleroma, :instance,
  name: "Asamblea Social",
  email: "no.contestar@asamblea.social",
  notify_email: "no.contestar@asamblea.social",
  limit: 5000,
  registrations_open: true
config :pleroma, :media_proxy,
  enabled: false,
  redirect_on_failure: true
config :pleroma, Pleroma.Repo,
  adapter: Ecto.Adapters.Postgres,
  username: "akkoma",
  password: System.get_env("AKKOMA_DB_PASSWORD"),
  database: "akkoma",
  hostname: "localhost"
config :web_push_encryption, :vapid_details,
  subject: "mailto:admin@asamblea.social",
  public_key: "BA2eDwn7j8NaiUFGqRl4Kw0pq1jJ6aqAKLpLf_JItGwdb7ahC3gdmgVA8epI1QQ56Z2d60KGt3UDP3_P6TU1JFQ",
  private_key: System.get_env("AKKOMA_VAPID_PRIVATE_KEY")
config :pleroma, :database, rum_enabled: false
config :pleroma, :instance, static_dir: "/var/lib/akkoma/static"
config :pleroma, Pleroma.Uploaders.Local, uploads: "/var/lib/akkoma/uploads"
config :joken, default_signer: System.get_env("AKKOMA_JOKEN_SIGNER")
config :pleroma, configurable_from_database: true
config :pleroma, Pleroma.Upload,
  filters: [Pleroma.Upload.Filter.Exiftool.ReadDescription, Pleroma.Upload.Filter.Exiftool.StripMetadata, Pleroma.Upload.Filter.AnonymizeFilename],
  base_url: "https://asamblea.social/media"
config :pleroma, Pleroma.Emails.Mailer,
  adapter: Swoosh.Adapters.SMTP,
  relay: "smtp.protonmail.ch",
  port: 587,
  username: "no.contestar@asamblea.social",
  password: System.get_env("AKKOMA_SMTP_PASSWORD"),
  ssl: false,
  tls: :always,
  auth: :always,
  enabled: true
