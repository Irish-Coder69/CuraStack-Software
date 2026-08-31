"""
DSM-5 / ICD-10 mental health diagnostic codes for CuraStack Software.
Format: (code, description, category)
"""

DSM_CODES = [
    # ── Depressive Disorders ──────────────────────────────────────────────────
    ("F32.0",  "Major depressive disorder, single episode, mild",                                  "Depressive"),
    ("F32.1",  "Major depressive disorder, single episode, moderate",                              "Depressive"),
    ("F32.2",  "Major depressive disorder, single episode, severe without psychosis",              "Depressive"),
    ("F32.3",  "Major depressive disorder, single episode, severe with psychotic features",        "Depressive"),
    ("F32.4",  "Major depressive disorder, single episode, in partial remission",                  "Depressive"),
    ("F32.5",  "Major depressive disorder, single episode, in full remission",                     "Depressive"),
    ("F32.9",  "Major depressive disorder, single episode, unspecified",                           "Depressive"),
    ("F32.A",  "Depression, unspecified",                                                          "Depressive"),
    ("F33.0",  "Major depressive disorder, recurrent, mild",                                       "Depressive"),
    ("F33.1",  "Major depressive disorder, recurrent, moderate",                                   "Depressive"),
    ("F33.2",  "Major depressive disorder, recurrent, severe without psychotic features",          "Depressive"),
    ("F33.3",  "Major depressive disorder, recurrent, severe with psychotic features",             "Depressive"),
    ("F33.40", "Major depressive disorder, recurrent, in remission, unspecified",                  "Depressive"),
    ("F33.9",  "Major depressive disorder, recurrent, unspecified",                                "Depressive"),
    ("F34.1",  "Dysthymic disorder (Persistent Depressive Disorder)",                              "Depressive"),
    ("F34.81", "Disruptive mood dysregulation disorder",                                           "Depressive"),
    ("F34.89", "Other specified depressive disorders",                                             "Depressive"),

    # ── Bipolar Disorders ─────────────────────────────────────────────────────
    ("F31.0",  "Bipolar I disorder, current or most recent episode hypomanic",                     "Bipolar"),
    ("F31.10", "Bipolar I disorder, current episode manic, unspecified severity",                  "Bipolar"),
    ("F31.11", "Bipolar I disorder, current episode manic, mild",                                  "Bipolar"),
    ("F31.12", "Bipolar I disorder, current episode manic, moderate",                              "Bipolar"),
    ("F31.13", "Bipolar I disorder, current episode manic, severe without psychotic features",     "Bipolar"),
    ("F31.14", "Bipolar I disorder, current episode manic, severe with psychotic features",        "Bipolar"),
    ("F31.31", "Bipolar I disorder, current episode depressed, mild",                              "Bipolar"),
    ("F31.32", "Bipolar I disorder, current episode depressed, moderate",                          "Bipolar"),
    ("F31.4",  "Bipolar I disorder, current episode depressed, severe, without psychotic features","Bipolar"),
    ("F31.5",  "Bipolar I disorder, current episode depressed, severe with psychotic features",    "Bipolar"),
    ("F31.81", "Bipolar II disorder",                                                              "Bipolar"),
    ("F31.9",  "Bipolar disorder, unspecified",                                                    "Bipolar"),
    ("F34.0",  "Cyclothymic disorder",                                                             "Bipolar"),

    # ── Anxiety Disorders ─────────────────────────────────────────────────────
    ("F40.00", "Agoraphobia, unspecified",                                                         "Anxiety"),
    ("F40.01", "Agoraphobia with panic disorder",                                                  "Anxiety"),
    ("F40.02", "Agoraphobia without panic disorder",                                               "Anxiety"),
    ("F40.10", "Social anxiety disorder (social phobia), unspecified",                             "Anxiety"),
    ("F40.11", "Social anxiety disorder, generalized",                                             "Anxiety"),
    ("F41.0",  "Panic disorder",                                                                   "Anxiety"),
    ("F41.1",  "Generalized anxiety disorder",                                                     "Anxiety"),
    ("F41.3",  "Other mixed anxiety disorders",                                                    "Anxiety"),
    ("F41.9",  "Anxiety disorder, unspecified",                                                    "Anxiety"),
    ("F40.218","Phobia, other",                                                                    "Anxiety"),
    ("F40.8",  "Other specified phobic disorders",                                                 "Anxiety"),
    ("F93.0",  "Separation anxiety disorder of childhood",                                         "Anxiety"),

    # ── OCD & Related ─────────────────────────────────────────────────────────
    ("F42.2",  "Mixed obsessional thoughts and acts",                                              "OCD/Related"),
    ("F42.3",  "Hoarding disorder",                                                                "OCD/Related"),
    ("F42.4",  "Excoriation (skin-picking) disorder",                                              "OCD/Related"),
    ("F42.8",  "Other obsessive-compulsive disorder",                                              "OCD/Related"),
    ("F42.9",  "Obsessive-compulsive disorder, unspecified",                                       "OCD/Related"),
    ("F45.22", "Body dysmorphic disorder",                                                         "OCD/Related"),
    ("F63.3",  "Trichotillomania",                                                                 "OCD/Related"),

    # ── Trauma & Stress ───────────────────────────────────────────────────────
    ("F43.10", "Post-traumatic stress disorder, unspecified",                                      "Trauma"),
    ("F43.11", "Post-traumatic stress disorder, acute",                                            "Trauma"),
    ("F43.12", "Post-traumatic stress disorder, chronic",                                          "Trauma"),
    ("F43.20", "Adjustment disorder, unspecified",                                                 "Trauma"),
    ("F43.21", "Adjustment disorder with depressed mood",                                          "Trauma"),
    ("F43.22", "Adjustment disorder with anxiety",                                                 "Trauma"),
    ("F43.23", "Adjustment disorder with mixed anxiety and depressed mood",                        "Trauma"),
    ("F43.24", "Adjustment disorder with disturbance of conduct",                                  "Trauma"),
    ("F43.25", "Adjustment disorder with mixed disturbance of emotions and conduct",               "Trauma"),
    ("F43.8",  "Other reactions to severe stress",                                                 "Trauma"),
    ("F43.9",  "Reaction to severe stress, unspecified",                                           "Trauma"),

    # ── Dissociative ──────────────────────────────────────────────────────────
    ("F44.0",  "Dissociative amnesia",                                                             "Dissociative"),
    ("F44.1",  "Dissociative fugue",                                                               "Dissociative"),
    ("F44.81", "Dissociative identity disorder",                                                   "Dissociative"),
    ("F44.89", "Other dissociative and conversion disorders",                                      "Dissociative"),
    ("F48.1",  "Depersonalization-derealization syndrome",                                         "Dissociative"),

    # ── Somatic / Functional ──────────────────────────────────────────────────
    ("F45.0",  "Somatization disorder",                                                            "Somatic"),
    ("F45.1",  "Undifferentiated somatoform disorder",                                             "Somatic"),
    ("F45.20", "Hypochondriacal disorder, unspecified",                                            "Somatic"),
    ("F45.41", "Chronic pain disorder with related psychological factors",                         "Somatic"),
    ("F45.8",  "Other somatoform disorders",                                                       "Somatic"),
    ("F45.9",  "Somatoform disorder, unspecified",                                                 "Somatic"),

    # ── Psychotic Disorders ───────────────────────────────────────────────────
    ("F20.9",  "Schizophrenia, unspecified",                                                       "Psychotic"),
    ("F21",    "Schizotypal disorder",                                                             "Psychotic"),
    ("F22",    "Delusional disorder",                                                              "Psychotic"),
    ("F23",    "Brief psychotic disorder",                                                         "Psychotic"),
    ("F25.0",  "Schizoaffective disorder, bipolar type",                                           "Psychotic"),
    ("F25.1",  "Schizoaffective disorder, depressive type",                                        "Psychotic"),
    ("F25.9",  "Schizoaffective disorder, unspecified",                                            "Psychotic"),
    ("F28",    "Other psychotic disorder not due to a substance or known physiological condition", "Psychotic"),
    ("F29",    "Unspecified psychosis not due to a substance or known physiological condition",    "Psychotic"),

    # ── Personality Disorders ─────────────────────────────────────────────────
    ("F60.0",  "Paranoid personality disorder",                                                    "Personality"),
    ("F60.1",  "Schizoid personality disorder",                                                    "Personality"),
    ("F60.2",  "Antisocial personality disorder",                                                  "Personality"),
    ("F60.3",  "Borderline personality disorder",                                                  "Personality"),
    ("F60.4",  "Histrionic personality disorder",                                                  "Personality"),
    ("F60.5",  "Obsessive-compulsive personality disorder",                                        "Personality"),
    ("F60.6",  "Avoidant personality disorder",                                                    "Personality"),
    ("F60.7",  "Dependent personality disorder",                                                   "Personality"),
    ("F60.81", "Narcissistic personality disorder",                                                "Personality"),
    ("F60.89", "Other specific personality disorders",                                             "Personality"),
    ("F60.9",  "Personality disorder, unspecified",                                                "Personality"),

    # ── Eating Disorders ──────────────────────────────────────────────────────
    ("F50.00", "Anorexia nervosa, unspecified",                                                    "Eating"),
    ("F50.01", "Anorexia nervosa, restricting type",                                               "Eating"),
    ("F50.02", "Anorexia nervosa, binge eating/purging type",                                      "Eating"),
    ("F50.2",  "Bulimia nervosa",                                                                  "Eating"),
    ("F50.81", "Binge-eating disorder",                                                            "Eating"),
    ("F50.82", "Avoidant/restrictive food intake disorder",                                        "Eating"),
    ("F50.89", "Other specified eating disorder",                                                  "Eating"),
    ("F50.9",  "Eating disorder, unspecified",                                                     "Eating"),

    # ── ADHD / Neurodevelopmental ─────────────────────────────────────────────
    ("F90.0",  "ADHD, predominantly inattentive type",                                             "ADHD"),
    ("F90.1",  "ADHD, predominantly hyperactive-impulsive type",                                   "ADHD"),
    ("F90.2",  "ADHD, combined type",                                                              "ADHD"),
    ("F90.8",  "Other ADHD",                                                                       "ADHD"),
    ("F90.9",  "ADHD, unspecified type",                                                           "ADHD"),
    ("F84.0",  "Autism spectrum disorder",                                                         "Neurodevelopmental"),
    ("F84.5",  "Asperger syndrome",                                                                "Neurodevelopmental"),
    ("F80.0",  "Phonological disorder",                                                            "Neurodevelopmental"),
    ("F80.9",  "Language disorder, unspecified",                                                   "Neurodevelopmental"),
    ("F81.0",  "Specific reading disorder",                                                        "Neurodevelopmental"),
    ("F82",    "Specific developmental disorder of motor function",                                "Neurodevelopmental"),

    # ── Substance Use ─────────────────────────────────────────────────────────
    ("F10.10", "Alcohol use disorder, mild",                                                       "Substance"),
    ("F10.20", "Alcohol use disorder, moderate/severe",                                            "Substance"),
    ("F11.10", "Opioid use disorder, mild",                                                        "Substance"),
    ("F11.20", "Opioid use disorder, moderate/severe",                                             "Substance"),
    ("F12.10", "Cannabis use disorder, mild",                                                      "Substance"),
    ("F12.20", "Cannabis use disorder, moderate/severe",                                           "Substance"),
    ("F14.10", "Cocaine use disorder, mild",                                                       "Substance"),
    ("F15.10", "Stimulant use disorder, mild",                                                     "Substance"),
    ("F19.10", "Other psychoactive substance use disorder, mild",                                  "Substance"),
    ("F17.210","Nicotine dependence, cigarettes, uncomplicated",                                   "Substance"),

    # ── Sleep ─────────────────────────────────────────────────────────────────
    ("F51.01", "Primary insomnia",                                                                 "Sleep"),
    ("F51.11", "Primary hypersomnia, not due to a substance",                                      "Sleep"),
    ("G47.00", "Insomnia, unspecified",                                                            "Sleep"),
    ("G47.10", "Hypersomnia, unspecified",                                                         "Sleep"),
    ("F51.4",  "Sleep terrors",                                                                    "Sleep"),
    ("F51.5",  "Nightmare disorder",                                                               "Sleep"),

    # ── Childhood / Behavioral ────────────────────────────────────────────────
    ("F91.0",  "Conduct disorder confined to family context",                                      "Childhood/Behavioral"),
    ("F91.1",  "Unsocialized conduct disorder",                                                    "Childhood/Behavioral"),
    ("F91.2",  "Socialized conduct disorder",                                                      "Childhood/Behavioral"),
    ("F91.3",  "Oppositional defiant disorder",                                                    "Childhood/Behavioral"),
    ("F91.9",  "Conduct disorder, unspecified",                                                    "Childhood/Behavioral"),
    ("F93.0",  "Separation anxiety disorder",                                                      "Childhood/Behavioral"),
    ("F94.0",  "Selective mutism",                                                                 "Childhood/Behavioral"),
    ("F98.0",  "Enuresis not due to a substance or known physiological condition",                 "Childhood/Behavioral"),

    # ── Grief / Bereavement ───────────────────────────────────────────────────
    ("Z63.4",  "Disappearance and death of family member",                                         "Grief/Bereavement"),
    ("F43.21", "Adjustment disorder with depressed mood (bereavement)",                            "Grief/Bereavement"),

    # ── Relationship / Z-Codes ────────────────────────────────────────────────
    ("Z63.0",  "Problems in relationship with spouse or partner",                                  "Z-Code/Social"),
    ("Z63.8",  "Other specified problems related to primary support group",                        "Z-Code/Social"),
    ("Z65.3",  "Problems related to other legal circumstances",                                    "Z-Code/Social"),
    ("Z65.4",  "Victim of crime and terrorism",                                                    "Z-Code/Social"),
    ("Z71.89", "Other specified counseling",                                                       "Z-Code/Social"),
    ("Z72.9",  "Problem related to lifestyle, unspecified",                                        "Z-Code/Social"),
    ("Z03.89", "Encounter for observation for other suspected diseases ruled out",                 "Z-Code/Social"),
    ("Z04.89", "Encounter for examination and observation for other specified reasons",            "Z-Code/Social"),

    # ── Unspecified ───────────────────────────────────────────────────────────
    ("F99",    "Mental disorder, not otherwise specified",                                         "Unspecified"),
    ("F09",    "Unspecified organic or symptomatic mental disorder",                               "Unspecified"),
]
