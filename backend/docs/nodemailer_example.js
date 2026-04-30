// Optional NodeMailer integration example (standalone).
// Run in a Node environment with: npm i nodemailer

const nodemailer = require("nodemailer");

async function sendEmailWithNodeMailer({ to, subject, body }) {
  const transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST || "smtp.gmail.com",
    port: Number(process.env.SMTP_PORT || 587),
    secure: false,
    auth: {
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASSWORD,
    },
  });

  const info = await transporter.sendMail({
    from: process.env.SMTP_FROM || process.env.SMTP_USER,
    to,
    subject,
    text: body,
    html: body.replace(/\n/g, "<br/>"),
  });

  return { messageId: info.messageId, accepted: info.accepted, rejected: info.rejected };
}

module.exports = { sendEmailWithNodeMailer };
