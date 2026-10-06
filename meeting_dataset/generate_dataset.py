#!/usr/bin/env python3
"""Synthetic meeting-transcript dataset with ground-truth JSON.

Every transcript is composed from labelled "segments". Each segment emits
dialogue lines AND the matching ground truth, so labels always agree with the
text. Usage:  python generate_dataset.py --n 60 --seed 42 --out .
"""
import argparse
import calendar
import csv
import json
import os
import random
from datetime import date, timedelta

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SPEAKERS = ["Aarav", "Meena", "Karthik", "Divya", "Arun", "Priya", "Dev", "Nisha", "Manoj",
            "Kavya", "Riya", "Lena", "Tom", "Harini", "Vikram", "Anjali", "Faizal", "Swetha",
            "Naveen", "Pooja", "Imran", "Deepak"]
ABSENT = ["Ravi", "Prof. Anand", "Dr. Lakshmi", "Ms. Geetha", "Mr. Selvam"]

# ---------------------------------------------------------------- deadlines
def iso(d):
    return d.isoformat()


def next_weekday(a, wd):
    delta = (wd - a.weekday()) % 7 or 7
    return a + timedelta(days=delta)


def next_monday(a):
    return a + timedelta(days=7 - a.weekday())


def _month_bounds_next(a):
    first = (a.replace(day=1) + timedelta(days=32)).replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return iso(first) + "/" + iso(last)


RESOLVABLE = [
    ("tomorrow", lambda a: iso(a + timedelta(days=1))),
    ("by tomorrow", lambda a: iso(a + timedelta(days=1))),
    ("today", lambda a: iso(a)),
    ("by end of day", lambda a: iso(a)),
    ("in two days", lambda a: iso(a + timedelta(days=2))),
    ("in three days", lambda a: iso(a + timedelta(days=3))),
    ("by next Friday", lambda a: iso(next_monday(a) + timedelta(days=4))),
    ("next week", lambda a: iso(next_monday(a)) + "/" + iso(next_monday(a) + timedelta(days=6))),
    ("this weekend", lambda a: iso(a + timedelta(days=5 - a.weekday())) + "/" + iso(a + timedelta(days=6 - a.weekday()))),
    ("by the end of the month", lambda a: iso(a.replace(day=calendar.monthrange(a.year, a.month)[1]))),
    ("next month", _month_bounds_next),
]
for _i in range(5):
    RESOLVABLE.append(("by " + WEEKDAYS[_i], lambda a, i=_i: iso(next_weekday(a, i))))
    RESOLVABLE.append(("by " + WEEKDAYS[_i], lambda a, i=_i: iso(next_weekday(a, i))))  # weight weekday phrases x2

NULLISH = ["after the review", "once the budget is approved", "before the demo",
           "when the hall is confirmed"]

# --------------------------------------------------------------------- pools
TECH = [
    ("test the prototype", "tested the prototype"),
    ("fix the login bug", "fixed the login bug"),
    ("deploy the staging build", "deployed the staging build"),
    ("write the API documentation", "written the API documentation"),
    ("review the pull request", "reviewed the pull request"),
    ("clean the training dataset", "cleaned the training dataset"),
    ("set up the CI pipeline", "set up the CI pipeline"),
    ("benchmark the model", "benchmarked the model"),
    ("update the README", "updated the README"),
    ("record the demo video", "recorded the demo video"),
    ("prepare the demo script", "prepared the demo script"),
    ("migrate the database", "migrated the database"),
    ("write the unit tests", "written the unit tests"),
    ("label the sample transcripts", "labelled the sample transcripts"),
    ("compile the final report", "compiled the final report"),
    ("upload the code to the repository", "uploaded the code to the repository"),
    ("renew the domain", "renewed the domain"),
    ("set up the Slack channel", "set up the Slack channel"),
    ("test the mobile layout", "tested the mobile layout"),
    ("organise the shared drive", "organised the shared drive"),
    ("check the audio setup", "checked the audio setup"),
    ("set up the registration page", "set up the registration page"),
]
EVENT = [
    ("prepare the slides", "prepared the slides"),
    ("design the poster", "designed the poster"),
    ("book the seminar hall", "booked the seminar hall"),
    ("email the faculty coordinator", "emailed the faculty coordinator"),
    ("send the agenda", "sent the agenda"),
    ("collect the registration forms", "collected the registration forms"),
    ("confirm the guest speaker", "confirmed the guest speaker"),
    ("arrange the projector", "arranged the projector"),
    ("print the certificates", "printed the certificates"),
    ("create the feedback form", "created the feedback form"),
    ("share the meeting notes", "shared the meeting notes"),
    ("update the budget sheet", "updated the budget sheet"),
    ("submit the permission letter", "submitted the permission letter"),
    ("contact the sponsors", "contacted the sponsors"),
    ("schedule the mock interview", "scheduled the mock interview"),
    ("publish the event announcement", "published the event announcement"),
    ("create the social media schedule", "created the social media schedule"),
    ("draft the press note", "drafted the press note"),
    ("reserve the cafeteria tables", "reserved the cafeteria tables"),
    ("collect the team photos", "collected the team photos"),
    ("verify the attendance sheet", "verified the attendance sheet"),
    ("create the invitation card", "created the invitation card"),
    ("follow up with the vendor", "followed up with the vendor"),
    ("arrange the transport", "arranged the transport"),
    ("prepare the judging rubric", "prepared the judging rubric"),
    ("collect the volunteer list", "collected the volunteer list"),
]
# (spoken after "Let's"/"We", decision text)
FIRM = [
    ("go with the dark theme for the poster", "Use the dark theme for the poster"),
    ("use Postgres for the database", "Use Postgres for the database"),
    ("hold the kickoff meeting on the 15th", "Hold the kickoff meeting on the 15th"),
    ("name the event Code Sprint", "Name the event Code Sprint"),
    ("keep the team size at four", "Keep the team size at four members"),
    ("use Google Forms for registration", "Use Google Forms for registration"),
    ("record all the sessions", "Record all sessions"),
    ("give certificates to all participants", "Give certificates to all participants"),
    ("run demo day in the lab", "Hold demo day in the lab"),
    ("use the shared drive for all documents", "Use the shared drive for all documents"),
    ("freeze the feature list today", "Freeze the feature list"),
    ("limit each pitch to five minutes", "Limit each pitch to five minutes"),
    ("meet every Wednesday", "Meet every Wednesday"),
]
# (proposal, counter, decision)
REJECT = [
    ("change the venue to the auditorium", "keep the current venue", "Keep the current venue"),
    ("move the event to Saturday", "stay with Friday", "Hold the event on Friday"),
    ("switch to Python for the backend", "stick with Java", "Stay with Java for the backend"),
    ("use a paid hosting plan", "stay on the free tier", "Stay on the free hosting tier"),
    ("add a third round to the contest", "keep it to two rounds", "Keep the contest to two rounds"),
    ("print the brochures in colour", "keep them black and white", "Print brochures in black and white"),
    ("redo the logo from scratch", "keep the existing logo", "Keep the existing logo"),
    ("extend registration by a week", "close registration on the original date", "Close registration on the original date"),
    ("cut the workshop to one hour", "keep the full two hours", "Keep the workshop at two hours"),
    ("move the weekly meeting to mornings", "keep the evening slot", "Keep the weekly meeting in the evening"),
]
# (retracted commitment, reason, decision)
RETRACT = [
    ("order the T-shirts", "the budget is tight", "No T-shirts this time"),
    ("book the catering", "the budget is tight", "No catering"),
    ("print the brochures", "we're going digital only", "Go digital only, no printed brochures"),
    ("arrange the guest lecture", "the speaker pulled out", "Drop the guest lecture"),
    ("set up the photo booth", "there's no space", "Skip the photo booth"),
    ("create the souvenir kits", "we don't have the funds", "Drop the souvenir kits"),
    ("hire the sound system", "the hall already has one", "Use the hall's built-in sound system"),
]
# (option A, option B, thing being chosen)
TENT_CHOICE = [
    ("Postgres", "MongoDB", "the database"),
    ("Flutter", "React Native", "the mobile app"),
    ("Saturday", "Sunday", "the hackathon date"),
    ("Seminar Hall A", "the auditorium", "the venue"),
    ("a hybrid format", "a fully offline format", "the event format"),
    ("Whisper", "a cloud speech API", "speech-to-text"),
    ("round robin", "knockout", "the contest format"),
]
# (tentative action, condition, unresolved label)
TENT_COND = [
    ("hold the finals on Saturday", "the hall is free",
     "Finals date (Saturday) tentative, pending hall availability"),
    ("open registration on Monday", "the form is approved",
     "Registration opening on Monday tentative, pending form approval"),
    ("start the training sessions on the 12th", "the lab access is sorted",
     "Training start on the 12th tentative, pending lab access"),
]
# (spoken, unresolved label)
UNRESOLVED = [
    ("The budget is still not approved.", "Budget is not yet approved"),
    ("We still don't have confirmation from the venue.", "Venue confirmation not received"),
    ("Nobody knows who is judging the final round.", "Judges for the final round not identified"),
    ("The sponsor hasn't replied to our email.", "Sponsor has not replied"),
    ("The API key request is still stuck with the admin office.", "API key request still pending with the admin office"),
    ("We haven't figured out how to handle the audio echo in the hall.", "Audio echo in the hall not resolved"),
    ("The lab access letter still has no signature.", "Lab access letter still unsigned"),
    ("We don't know how many people will actually turn up.", "Expected attendance unknown"),
    ("The model accuracy is still stuck below the target.", "Model accuracy still below target"),
    ("The deployment keeps failing and we don't know why.", "Cause of recurring deployment failure unknown"),
    ("The dataset licence is unclear.", "Dataset licence unclear"),
    ("Parking arrangements for guests are still open.", "Guest parking arrangements still open"),
    ("How do we handle late registrations? No idea yet.", "Handling of late registrations undecided"),
    ("Who covers the helpdesk on day two? That's still open.", "Helpdesk coverage for day two undecided"),
]

NOISE = ["Sorry to cut in, my mic was muted for a moment.",
         "Hold on, someone is at the door, one second.",
         "Sorry, can you repeat that? The audio dropped.",
         "Sorry, I lost the call for a second."]
ACKS = ["Great, thanks.", "Okay.", "Good.", "Noted.", "Alright."]
GENERIC_FILLERS = ["Okay, moving on.", "Right, that makes sense.", "Can everyone see my screen?",
                   "Sorry, I was on mute.", "Yeah, I agree with that.", "Hmm, interesting.",
                   "Did anyone watch the match last night?", "It's so hot in this room today.",
                   "The Wi-Fi here is terrible again.", "Let me pull up the notes.",
                   "Okay, next point.", "Fair enough."]

STYLES = {
    "standup": dict(title="Daily standup", tech=0.8,
        w=dict(vol=4, assigned=2, unassigned=1, third=1, reassign=1, correction=1, completed=5, hedge=1, firm=.5, reject=.3, retract=.2, tchoice=.3, tcond=.3, unres=4),
        openers=["Okay, quick standup, let's go around the room."],
        fillers=["Nothing else from my side.", "Same here, just continuing the ongoing work.", "Alright, who's next?"],
        closers=["That's all for today.", "Okay, see you all tomorrow."]),
    "club_planning": dict(title="Club event planning", tech=0.15,
        w=dict(vol=3, assigned=3, unassigned=2, third=2, reassign=1, correction=1.5, completed=1, hedge=.5, firm=3, reject=2.5, retract=1.5, tchoice=1, tcond=1, unres=2),
        openers=["Alright everyone, let's plan the upcoming event."],
        fillers=["The turnout last time was good, wasn't it?", "Let's keep it simple this year.", "I like that idea."],
        closers=["Great meeting, everyone. Thanks for coming.", "Okay, let's wrap up here."]),
    "project_review": dict(title="Project review", tech=0.9,
        w=dict(vol=2, assigned=2, unassigned=1.5, third=1, reassign=.5, correction=1, completed=2, hedge=1, firm=2, reject=1.5, retract=.3, tchoice=2.5, tcond=1, unres=3.5),
        openers=["Let's start the project review and go through where we stand."],
        fillers=["The latest numbers look better than last week.", "I'll leave the details for the report.", "Let's keep the discussion focused."],
        closers=["Okay, that covers the review.", "Thanks all, let's close the review."]),
    "brainstorm": dict(title="Brainstorm", tech=0.5,
        w=dict(vol=1.5, assigned=1, unassigned=3, third=.5, reassign=.3, correction=.5, completed=.3, hedge=3, firm=1.5, reject=3, retract=1, tchoice=2.5, tcond=2, unres=2),
        openers=["Okay, open floor, throw out any ideas you have."],
        fillers=["That's a wild idea, I love it.", "Let's not filter ourselves yet.", "Interesting angle, keep going."],
        closers=["Good ideas today, thanks everyone.", "Alright, let's stop here for today."]),
    "sprint_planning": dict(title="Sprint planning", tech=0.95,
        w=dict(vol=3, assigned=4, unassigned=2, third=2, reassign=1.5, correction=2, completed=1, hedge=.5, firm=2, reject=1, retract=.3, tchoice=1, tcond=1, unres=2),
        openers=["Welcome to sprint planning, let's go through the backlog."],
        fillers=["That ticket is bigger than it looks.", "Let's size it later.", "The backlog is getting long."],
        closers=["Sprint is set, thanks everyone.", "That's the plan for this sprint."]),
    "hackathon_sync": dict(title="Hackathon sync", tech=0.7,
        w=dict(vol=3, assigned=2, unassigned=2, third=1, reassign=1, correction=1.5, completed=2, hedge=1, firm=2, reject=1.5, retract=.5, tchoice=1.5, tcond=1.5, unres=3),
        openers=["Team, quick sync before the hackathon, let's be fast."],
        fillers=["We're running out of time.", "Coffee run anyone?", "The demo needs to be rock solid."],
        closers=["Okay, back to work everyone.", "Good sync, let's go."]),
    "faculty_advisor": dict(title="Faculty advisor meeting", tech=0.5,
        w=dict(vol=2, assigned=2, unassigned=1, third=1, reassign=.3, correction=1, completed=1, hedge=.5, firm=1.5, reject=1, retract=.5, tchoice=2, tcond=2.5, unres=3.5),
        openers=["Good afternoon, shall we begin with the progress update?"],
        fillers=["That's a fair point.", "We should keep the department's guidelines in mind.", "Please continue."],
        closers=["Thank you all, that will be all for today.", "Good, let's meet again soon."]),
    "retrospective": dict(title="Retrospective", tech=0.6,
        w=dict(vol=1.5, assigned=1, unassigned=2, third=.5, reassign=.3, correction=.5, completed=4, hedge=1.5, firm=3, reject=1.5, retract=1, tchoice=.5, tcond=.5, unres=3),
        openers=["Let's start the retro, what went well and what didn't?"],
        fillers=["That went better than I expected.", "I think we all felt that.", "Let's be honest about it."],
        closers=["Thanks for the honest feedback.", "Good retro, everyone."]),
    "event_ops": dict(title="Event operations", tech=0.1,
        w=dict(vol=3, assigned=3, unassigned=2.5, third=2, reassign=2, correction=2, completed=2, hedge=.5, firm=2, reject=2, retract=2.5, tchoice=1, tcond=2, unres=3),
        openers=["Okay, event day is close, let's walk through the logistics."],
        fillers=["Logistics always get messy.", "Let's double check everything.", "Remember last year's chaos?"],
        closers=["Alright, that's the logistics.", "Thanks team, let's make it a good one."]),
    "client_call": dict(title="Client call", tech=0.7,
        w=dict(vol=2.5, assigned=2, unassigned=1, third=1, reassign=.5, correction=3, completed=1, hedge=1, firm=2, reject=1.5, retract=.5, tchoice=1.5, tcond=2, unres=3.5),
        openers=["Thanks for joining the call, let's go through the open items."],
        fillers=["Understood, thanks for clarifying.", "Let me note that down.", "That's helpful context."],
        closers=["Thanks for your time, everyone.", "Great, we'll talk again soon."]),
}

NAMES = set(SPEAKERS) | {"Prof.", "Dr.", "Ms.", "Mr.", "Ravi", "Postgres", "Whisper", "Flutter", "API"}

TIERS = {"medium": (8, (3, 4)), "long": (12, (4, 5)), "very_long": (18, (5, 7))}


def sp(base, phrase):
    return base if not phrase else base + " " + phrase


def cap(s):
    return s[0].upper() + s[1:]


def item(base, owner, phrase, iso_, status="pending"):
    return {"task": cap(base), "owner": owner, "deadline": phrase, "deadline_iso": iso_, "status": status}


class Ctx:
    def __init__(self, rnd, speakers, anchor, style):
        self.r, self.speakers, self.anchor, self.style = rnd, speakers, anchor, style
        self.tech, self.event = TECH[:], EVENT[:]
        rnd.shuffle(self.tech)
        rnd.shuffle(self.event)
        self.pools = {k: v[:] for k, v in dict(firm=FIRM, reject=REJECT, retract=RETRACT,
                                               tchoice=TENT_CHOICE, tcond=TENT_COND, unres=UNRESOLVED).items()}
        for v in self.pools.values():
            rnd.shuffle(v)
        wd = WEEKDAYS[anchor.weekday()]
        self.resolvable = [x for x in RESOLVABLE if not x[0].endswith(wd)]

    def spk(self, *excl):
        return self.r.choice([s for s in self.speakers if s not in excl])

    def task(self):
        first, second = (self.tech, self.event) if self.r.random() < STYLES[self.style]["tech"] else (self.event, self.tech)
        for pool in (first, second):
            if pool:
                return pool.pop()
        return None

    def take(self, name):
        return self.pools[name].pop() if self.pools[name] else None

    def dl(self, resolvable=False):
        if not resolvable and self.r.random() < 0.12:
            return None, None
        if not resolvable and self.r.random() < 0.2:
            return self.r.choice(NULLISH), None
        p, f = self.r.choice(self.resolvable)
        return p, f(self.anchor)


def seg(lines, actions=(), decisions=(), unresolved=()):
    return dict(lines=list(lines), actions=list(actions), decisions=list(decisions), unresolved=list(unresolved))


def s_vol(c):
    t = c.task()
    if not t:
        return None
    base, _ = t
    o = c.spk()
    p, i = c.dl()
    if p and c.r.random() < 0.25:
        x = c.spk(o)
        lines = [(o, f"I'll {base} --"), (x, c.r.choice(NOISE)), (o, f"Sorry, as I was saying, {p}.")]
    else:
        form = c.r.choice(["I'll {}.", "I can {}.", "Let me {}."])
        lines = [(o, form.format(sp(base, p)))]
    if c.r.random() < .5:
        lines.append((c.spk(o), c.r.choice(ACKS)))
    return seg(lines, [item(base, o, p, i)])


def s_assigned(c):
    t = c.task()
    if not t:
        return None
    base, _ = t
    o = c.spk()
    a = c.spk(o)
    p, i = c.dl()
    f = c.r.randrange(4)
    if f == 0 or (f == 1 and not p):
        lines = [(a, f"{o}, can you {sp(base, p)}?"), (o, c.r.choice(["Sure, I'll do that.", "Yes, will do.", "No problem."]))]
    elif f == 1:
        lines = [(a, f"{o}, can you {base}?"), (o, f"Yes, I can do that {p}.")]
    elif f == 2:
        lines = [(a, f"I'd like {o} to {sp(base, p)}."), (o, "Okay, noted.")]
    else:
        lines = [(a, f"{o}, could you {sp(base, p)}?"), (o, "Yes, no problem.")]
    return seg(lines, [item(base, o, p, i)])


def s_unassigned(c):
    t = c.task()
    if not t:
        return None
    base, _ = t
    a = c.spk()
    p, i = c.dl()
    f = c.r.randrange(3)
    first = [f"Someone needs to {sp(base, p)}.",
             f"We still need to {sp(base, p)}, but nobody has picked it up.",
             f"Who's going to {sp(base, p)}?"][f]
    lines = [(a, first), (c.spk(a), c.r.choice(["Yeah, that's true.", "Not me, I'm swamped this week.",
                                                  "Let's see who has time.", "I'm not free for that, sorry."]))]
    return seg(lines, [item(base, None, p, i)])


def s_third(c):
    t = c.task()
    if not t:
        return None
    base, _ = t
    o = c.spk()
    a = c.spk(o)
    p, i = c.dl()
    first = c.r.choice([f"{o} will {sp(base, p)}, right?", f"{o} is going to {sp(base, p)}."])
    return seg([(a, first), (o, c.r.choice(["Right, that's me.", "Yes, that's right."]))], [item(base, o, p, i)])


def s_reassign(c):
    t = c.task()
    if not t or len(c.speakers) < 3:
        return None
    base, _ = t
    o1 = c.spk()
    o2 = c.spk(o1)
    a = c.spk(o1, o2)
    p, i = c.dl()
    if c.r.random() < .5:
        lines = [(a, f"{o1}, can you {sp(base, p)}?"), (o1, "I'm swamped this week, sorry."), (o2, "I'll take it.")]
    else:
        lines = [(a, f"{o1}, you {sp(base, p)}."), (o1, f"{o2} knows that part better, honestly."),
                 (a, f"Fair enough. {o2}, you take it."), (o2, "Okay.")]
    return seg(lines, [item(base, o2, p, i)])


def s_correction(c):
    t = c.task()
    if not t:
        return None
    base, _ = t
    o = c.spk()
    a = c.spk(o)
    p1, _i1 = c.dl(resolvable=True)
    while True:
        p2, i2 = c.dl(resolvable=True)
        if p2 != p1:
            break
    if c.r.random() < .5:
        reason = c.r.choice(["the lab is closed till then", "the review is before that", "everyone is busy until then"])
        lines = [(o, f"I'll {sp(base, p1)}."), (a, f"Sorry, make it {p2}, {reason}."), (o, f"Right, {p2} then.")]
    else:
        lines = [(o, f"I'll {sp(base, p1)} --"), (a, f"Actually, {p2}, I just checked the calendar."), (o, f"Okay, {p2}.")]
    return seg(lines, [item(base, o, p2, i2)])


def s_completed(c):
    t = c.task()
    if not t:
        return None
    base, past = t
    o = c.spk()
    a = c.spk(o)
    f = c.r.randrange(3)
    if f == 0:
        lines = [(a, f"Did anyone {base}?"), (o, "I did, yesterday.")]
        it = item(base, o, "yesterday", iso(c.anchor - timedelta(days=1)), "completed")
    elif f == 1:
        lines = [(a, f"Did anyone {base}?"), (o, f"I've already {past}.")]
        it = item(base, o, None, None, "completed")
    else:
        lines = [(o, f"Quick update: I've {past}.")]
        it = item(base, o, None, None, "completed")
    return seg(lines, [it])


def s_hedge(c):
    t = c.task()
    if not t:
        return None
    base, _ = t
    o = c.spk()
    a = c.spk(o)
    if c.r.random() < .5:
        lines = [(o, f"If I get time, I might {base}."), (a, "Okay, no pressure.")]
    else:
        lines = [(o, f"We could {base} if we had more people, but we don't."), (a, "True, let's leave it.")]
    return seg(lines)


def s_firm(c):
    d = c.take("firm")
    if not d:
        return None
    spoken, dec = d
    a = c.spk()
    b = c.spk(a)
    first = f"Let's {spoken}." if c.r.random() < .5 else f"Okay, final call. We {spoken}."
    return seg([(a, first), (b, c.r.choice(["Agreed.", "Works for me.", "Fine by me.", "Sounds good."]))], decisions=[dec])


def s_reject(c):
    d = c.take("reject")
    if not d:
        return None
    alt, keep, dec = d
    a = c.spk()
    b = c.spk(a)
    return seg([(a, f"Maybe we should {alt}."), (b, f"No, let's {keep}."), (a, "Okay, fair.")], decisions=[dec])


def s_retract(c):
    d = c.take("retract")
    if not d:
        return None
    verb, reason, dec = d
    o = c.spk()
    a = c.spk(o)
    return seg([(o, f"I'll {verb}."), (o, f"Actually no, forget it, {reason}."), (a, "Okay, then we skip it.")], decisions=[dec])


def s_tchoice(c):
    d = c.take("tchoice")
    if not d:
        return None
    A, B, noun = d
    z = c.r.choice(ABSENT)
    day = c.r.choice(WEEKDAYS[:5])
    p = c.spk()
    dv = c.spk(p)
    lines = [(p, f"Should we pick {A} or {B} for {noun}?"),
             (dv, f"I lean {A}, but let's confirm with {z} first."),
             (p, f"{z} is out till {day}, so we decide then.")]
    acts = []
    t = c.task() if c.r.random() < .5 else None
    if t:
        base, _ = t
        ph, i = c.dl()
        lines.append((dv, f"Fine. I'll {sp(base, ph)}, either way."))
        acts.append(item(base, dv, ph, i))
    return seg(lines, acts, unresolved=[f"Choice between {A} and {B} for {noun} undecided, pending {z}'s input on {day}"])


def s_tcond(c):
    d = c.take("tcond")
    if not d:
        return None
    x, cond, label = d
    a = c.spk()
    b = c.spk(a)
    return seg([(a, f"Let's tentatively {x}, but only if {cond}."), (b, "Right, we'll confirm once we know.")], unresolved=[label])


def s_unres(c):
    d = c.take("unres")
    if not d:
        return None
    spoken, label = d
    a = c.spk()
    b = c.spk(a)
    return seg([(a, spoken), (b, c.r.choice(["Yeah, that's a worry.", "Let's park it for now.", "We'll revisit it."]))], unresolved=[label])


SEGS = dict(vol=s_vol, assigned=s_assigned, unassigned=s_unassigned, third=s_third, reassign=s_reassign,
            correction=s_correction, completed=s_completed, hedge=s_hedge, firm=s_firm, reject=s_reject,
            retract=s_retract, tchoice=s_tchoice, tcond=s_tcond, unres=s_unres)


def build(idx, rnd, used_dates):
    style = list(STYLES)[idx % len(STYLES)]
    tier = ["medium", "long", "very_long"][idx % 3]
    nseg, (lo, hi) = TIERS[tier]
    while True:
        d = date(2026, 9, 1) + timedelta(days=rnd.randrange(0, 110))
        if d.weekday() < 5 and d not in used_dates:
            used_dates.add(d)
            break
    attendees = rnd.sample(SPEAKERS, rnd.randint(lo, hi))
    st = STYLES[style]
    c = Ctx(rnd, attendees, d, style)
    chair = attendees[0]
    lines = [(chair, rnd.choice(st["openers"]))]
    actions, decisions, unresolved = [], [], []
    filler_pool = []
    kinds = list(st["w"])
    weights = [st["w"][k] for k in kinds]
    made = tries = 0
    while made < nseg and tries < 200:
        tries += 1
        s = SEGS[rnd.choices(kinds, weights)[0]](c)
        if not s:
            continue
        made += 1
        for _ in range(rnd.choice([0, 1, 1, 2])):
            if not filler_pool:
                filler_pool = st["fillers"] + GENERIC_FILLERS
                rnd.shuffle(filler_pool)
            lines.append((c.spk(), filler_pool.pop()))
        if rnd.random() < .12:
            a, b = rnd.sample(attendees, 2)
            lines += [(a, "Wait, can I--"), (b, "Go ahead."), (a, "Never mind, it can wait.")]
        lines += s["lines"]
        actions += s["actions"]
        decisions += s["decisions"]
        unresolved += s["unresolved"]
    lines.append((chair, rnd.choice(st["closers"])))
    out = []
    for n, (spk_, text) in enumerate(lines):
        if 0 < n < len(lines) - 1 and rnd.random() < .07 and not text.endswith("--"):
            first = text.split()[0].strip(",.?!")
            keep = first in NAMES or first.startswith("I'") or first == "I"
            text = rnd.choice(["Um, ", "So, ", "Yeah, so "]) + (text if keep else text[0].lower() + text[1:])
        out.append((spk_, text))
    pend = sum(a["status"] == "pending" for a in actions)
    done = len(actions) - pend
    unowned = sum(a["owner"] is None for a in actions)
    summary = (f"{st['title']} with {len(attendees)} attendees. "
               f"{len(decisions)} decision(s): {'; '.join(decisions[:3]) or 'none'}. "
               f"{len(unresolved)} open issue(s): {'; '.join(unresolved[:3]) or 'none'}. "
               f"{pend} pending and {done} completed action item(s), {unowned} without an owner.")
    gt = {"summary": summary, "action_items": actions, "decisions": decisions, "unresolved_issues": unresolved}
    return dict(id=f"meeting_{idx + 1:03d}", style=style, tier=tier, meeting_date=iso(d),
                weekday=WEEKDAYS[d.weekday()], attendees=attendees, turns=out, ground_truth=gt)


SEED_CASES = [
    ("seed_1", "Unassigned task, explicit owner, proposal vs final decision",
     "Riya: Someone needs to prepare the slides.\nManoj: I will test the prototype by Friday.\nKavya: The budget is still not approved.\nNisha: Maybe we should change the venue.\nNisha: No, let's keep the current venue.",
     {"summary": "Slides need an owner, Manoj will test the prototype, budget is pending, venue stays.",
      "action_items": [{"task": "Prepare the slides", "owner": None, "deadline": None, "deadline_iso": None, "status": "pending"},
                       {"task": "Test the prototype", "owner": "Manoj", "deadline": "by Friday", "deadline_iso": "2026-10-02", "status": "pending"}],
      "decisions": ["Keep the current venue"], "unresolved_issues": ["Budget is not yet approved"]}),
    ("seed_2", "Interruption and correction",
     "Arun: Report deadline is Monday...\nDivya: Sorry, Tuesday. Monday is a holiday.\nArun: Right. Divya, you send it.\nDivya: Sure. I already sent the client invite.",
     {"summary": "Divya will send the report by Tuesday; client invite already sent.",
      "action_items": [{"task": "Send the report", "owner": "Divya", "deadline": "Tuesday", "deadline_iso": "2026-10-06", "status": "pending"},
                       {"task": "Send the client invite", "owner": "Divya", "deadline": None, "deadline_iso": None, "status": "completed"}],
      "decisions": [], "unresolved_issues": []}),
    ("seed_3", "Multiple speakers, relative deadlines",
     "Meena: Karthik, can you book the lab tomorrow?\nKarthik: Yes. And I'll email the faculty next week.\nManoj: I'll update the poster after the review.\nMeena: Let's go with the dark theme for the poster.",
     {"summary": "Lab booking, faculty email and poster update assigned; dark theme chosen.",
      "action_items": [{"task": "Book the lab", "owner": "Karthik", "deadline": "tomorrow", "deadline_iso": "2026-10-02", "status": "pending"},
                       {"task": "Email the faculty", "owner": "Karthik", "deadline": "next week", "deadline_iso": "2026-10-05/2026-10-11", "status": "pending"},
                       {"task": "Update the poster", "owner": "Manoj", "deadline": "after the review", "deadline_iso": None, "status": "pending"}],
      "decisions": ["Use the dark theme for the poster"], "unresolved_issues": []}),
    ("seed_4", "Tentative decision, unresolved issue",
     "Priya: Postgres or MongoDB?\nDev: I lean Postgres, but let's confirm with Ravi.\nPriya: Ravi is out till Monday, so we decide then.\nDev: Fine. I'll draft the schema either way by Wednesday.",
     {"summary": "Database choice deferred until Ravi returns; Dev drafts schema meanwhile.",
      "action_items": [{"task": "Draft the schema", "owner": "Dev", "deadline": "by Wednesday", "deadline_iso": "2026-10-07", "status": "pending"}],
      "decisions": [], "unresolved_issues": ["Postgres vs MongoDB undecided, pending Ravi's input on Monday"]}),
    ("seed_5", "Completed work, retracted commitment",
     "Lena: Did anyone send the agenda?\nTom: I did, yesterday.\nLena: Who's handling catering?\nLena: I'll ask the office. Actually no, skip catering, budget's tight.",
     {"summary": "Agenda already sent; catering dropped.",
      "action_items": [{"task": "Send the agenda", "owner": "Tom", "deadline": "yesterday", "deadline_iso": "2026-09-30", "status": "completed"}],
      "decisions": ["No catering"], "unresolved_issues": []}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    for sub in ("transcripts", "ground_truth", "seed_cases"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    used, rows, dataset = set(), [], []
    for i in range(a.n):
        m = build(i, rnd, used)
        text = "\n".join(f"{s}: {t}" for s, t in m["turns"])
        header = (f"# {m['id']} | style: {m['style']} | date: {m['meeting_date']} ({m['weekday']}) "
                  f"| attendees: {', '.join(m['attendees'])}\n")
        with open(os.path.join(a.out, "transcripts", m["id"] + ".txt"), "w", encoding="utf-8") as f:
            f.write(header + text + "\n")
        with open(os.path.join(a.out, "ground_truth", m["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(m["ground_truth"], f, indent=2, ensure_ascii=False)
        gt = m["ground_truth"]
        dataset.append(dict(id=m["id"], style=m["style"], tier=m["tier"], meeting_date=m["meeting_date"],
                            weekday=m["weekday"], attendees=m["attendees"], transcript=text, ground_truth=gt))
        acts = gt["action_items"]
        rows.append([m["id"], m["style"], m["tier"], m["meeting_date"], m["weekday"], len(m["turns"]), len(m["attendees"]),
                     len(acts), sum(x["owner"] is None for x in acts), sum(x["status"] == "completed" for x in acts),
                     sum(x["deadline"] is not None and x["deadline_iso"] is None for x in acts),
                     len(gt["decisions"]), len(gt["unresolved_issues"])])
    with open(os.path.join(a.out, "dataset.jsonl"), "w", encoding="utf-8") as f:
        for d in dataset:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(os.path.join(a.out, "index.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "style", "tier", "meeting_date", "weekday", "n_turns", "n_speakers", "n_action_items",
                    "n_unassigned", "n_completed", "n_vague_deadlines", "n_decisions", "n_unresolved"])
        w.writerows(rows)
    with open(os.path.join(a.out, "seed_cases", "seed_cases.jsonl"), "w", encoding="utf-8") as f:
        for sid, desc, text, gt in SEED_CASES:
            f.write(json.dumps(dict(id=sid, description=desc, meeting_date="2026-10-01", weekday="Thursday",
                                    transcript=text, ground_truth=gt), ensure_ascii=False) + "\n")
    print(f"wrote {a.n} meetings to {a.out}")


if __name__ == "__main__":
    main()
