import { pulsePoll } from "./pulseDemoData.js";

export const PULSE_DEMO_STORAGE_KEY = "algowiki-pulse-demo-v1";

export function getLocalDateKey(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getMillisecondsUntilNextLocalDay(date = new Date()) {
  const nextDay = new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1);
  return Math.max(0, nextDay.getTime() - date.getTime());
}

export function createPulseDemoState(dateKey) {
  return {
    dateKey,
    firstVisitSeen: false,
    question: {
      completed: false,
      answer: "",
    },
    tickets: {
      reroll: 1,
      makeup: 1,
      superMakeup: 0,
    },
    challenge: {
      mode: null,
      drawIndex: 0,
      rerollsUsed: 0,
      completed: false,
    },
    poll: {
      completed: false,
      optionId: null,
    },
    points: 0,
  };
}

export function getPulseProgress(state) {
  return [state?.question?.completed, state?.challenge?.completed, state?.poll?.completed].filter(Boolean).length;
}

export function normalizePulseDemoState(candidate, dateKey) {
  const fresh = createPulseDemoState(dateKey);
  if (!candidate || candidate.dateKey !== dateKey) {
    return fresh;
  }

  const challengeMode =
    candidate.challenge?.mode === "A" || candidate.challenge?.mode === "B" ? candidate.challenge.mode : null;
  const pollOptionId = isPollOption(candidate.poll?.optionId) ? candidate.poll.optionId : null;
  const questionAnswer = typeof candidate.question?.answer === "string" ? candidate.question.answer.trim() : "";

  return {
    ...fresh,
    firstVisitSeen: Boolean(candidate.firstVisitSeen),
    question: {
      completed: Boolean(candidate.question?.completed && questionAnswer),
      answer: questionAnswer,
    },
    tickets: {
      reroll: toNonNegativeInteger(candidate.tickets?.reroll, fresh.tickets.reroll),
      makeup: toNonNegativeInteger(candidate.tickets?.makeup, fresh.tickets.makeup),
      superMakeup: toNonNegativeInteger(candidate.tickets?.superMakeup, fresh.tickets.superMakeup),
    },
    challenge: {
      mode: challengeMode,
      drawIndex: toNonNegativeInteger(candidate.challenge?.drawIndex, 0),
      rerollsUsed: Math.min(2, toNonNegativeInteger(candidate.challenge?.rerollsUsed, 0)),
      completed: Boolean(candidate.challenge?.completed && challengeMode),
    },
    poll: {
      completed: Boolean(candidate.poll?.completed && pollOptionId),
      optionId: pollOptionId,
    },
    points: toNonNegativeInteger(candidate.points, 0),
  };
}

export function reducePulseDemoState(state, action = {}) {
  const current = normalizePulseDemoState(state, state?.dateKey || action.dateKey);

  switch (action.type) {
    case "dismiss-first-visit":
      return { ...current, firstVisitSeen: true };

    case "answer-question": {
      const answer = String(action.answer || "").trim();
      if (!answer) return current;
      const firstCompletion = !current.question.completed;
      return {
        ...current,
        question: { completed: true, answer },
        tickets: {
          ...current.tickets,
          reroll: current.tickets.reroll + (firstCompletion ? 1 : 0),
        },
      };
    }

    case "choose-challenge": {
      if (current.challenge.mode || (action.mode !== "A" && action.mode !== "B")) return current;
      return {
        ...current,
        challenge: { ...current.challenge, mode: action.mode },
      };
    }

    case "reroll-challenge": {
      if (
        !current.challenge.mode ||
        current.challenge.completed ||
        current.challenge.rerollsUsed >= 2 ||
        current.tickets.reroll <= 0
      ) {
        return current;
      }
      return {
        ...current,
        tickets: { ...current.tickets, reroll: current.tickets.reroll - 1 },
        challenge: {
          ...current.challenge,
          drawIndex: current.challenge.drawIndex + 1,
          rerollsUsed: current.challenge.rerollsUsed + 1,
        },
      };
    }

    case "complete-challenge": {
      if (!current.challenge.mode || current.challenge.completed) return current;
      const reward = current.challenge.mode === "B" ? 3 : 1;
      return {
        ...current,
        challenge: { ...current.challenge, completed: true },
        points: current.points + reward,
      };
    }

    case "vote-poll": {
      if (current.poll.completed || !isPollOption(action.optionId)) return current;
      return {
        ...current,
        poll: { completed: true, optionId: action.optionId },
      };
    }

    case "reset":
      return createPulseDemoState(action.dateKey || current.dateKey);

    default:
      return current;
  }
}

function isPollOption(optionId) {
  return pulsePoll.options.some((option) => option.id === optionId);
}

function toNonNegativeInteger(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback;
}
