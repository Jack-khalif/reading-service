# Part C — Reading an Evaluation

## 1. Is 90.7% accuracy correct?

Arithmetically, yes: (18 + 889) / 1000 = 907 / 1000 = **90.7%**. But "correct"
and "meaningful" are different questions, and here the number is technically
correct and practically misleading. Only 80 of the 1,000 images (8%) are
actually positive. A model that predicts "negative" for every single image,
with zero clinical value whatsoever, would score 920/1000 = **92.0%**
accuracy — *higher* than this model. Accuracy on an imbalanced dataset is
dominated by how well you call the majority class, which tells you almost
nothing about how well you catch the minority class you actually care about.

## 2. What does it do well and badly? The right measures.

| Measure | Value | Meaning here |
|---|---|---|
| Sensitivity / Recall = TP/(TP+FN) | 18/80 = **22.5%** | Of everyone who actually has the condition, the model catches fewer than 1 in 4. It misses **62 of 80** true cases (77.5%). |
| Specificity = TN/(TN+FP) | 889/920 = **96.6%** | It's good at correctly clearing people who don't have it. |
| Precision / PPV = TP/(TP+FP) | 18/49 = **36.7%** | Of everyone it flags, less than 2 in 5 actually have the condition. |
| F1 | ≈ **27.9%** | Low, reflecting weak performance on both recall and precision together. |

Sensitivity and precision are the right measures here, not accuracy, because
this is a screening task on an imbalanced dataset with asymmetric costs
(explained below). The model is doing well at *ruling out* the condition
(high specificity) and doing badly at its actual job — *finding* it (low
sensitivity).

## 3. Given the harm profile, what would I change, and what would I need to know?

A missed case causes permanent harm; a positive flag only costs a clinician
a second look. That's a strongly asymmetric cost structure — false negatives
are far more expensive than false positives — so the model should be tuned
to **maximize sensitivity**, accepting a real drop in precision (more false
alarms) as the price. Concretely: get the model's raw scores (not just the
binary output), plot a sensitivity/specificity or precision/recall curve
across thresholds, and pick an operating point at, say, 90%+ sensitivity —
even though that will substantially increase false positives.

Before recommending a pilot I'd want to know: the score distribution so a
threshold can actually be chosen (not just the confusion matrix at whatever
threshold produced this table); how much false-positive volume the
downstream clinicians can absorb before alert fatigue sets in and they start
ignoring flags (which would defeat the whole point); whether performance
holds up on an external/prospective dataset rather than just this one test
set; and whether performance is even across relevant subgroups (age, sex,
imaging equipment, site) rather than concentrated in one group.

## 4. What would I have asked about the dataset before any of this?

How was ground truth established (biopsy/gold-standard confirmation vs. a
single reader's judgment, and how disagreements were resolved); how
representative the 8% positive prevalence is of the real screening
population (enriched test sets inflate precision, deflated ones understate
it); how the 1,000 images were collected — same sites/devices/populations
the model would see in deployment, or a narrower/cleaner source; and
whether 80 positive cases is even enough to trust these percentages — with
only 18 true positives, the 95% confidence interval on 22.5% sensitivity is
wide, wide enough that the "true" sensitivity could plausibly be
meaningfully higher or lower than this single table suggests.

## The specific problem, stated plainly

**This model misses more than three out of every four real cases of a
condition that causes permanent harm if missed, and its headline "90.7%
accurate" figure actively hides that fact because 92% of the test set is
negative.** It is not ready to pilot as-is; a screening tool for a
harm-if-missed condition needs to be evaluated and tuned on sensitivity,
not accuracy, and this one has not been.
